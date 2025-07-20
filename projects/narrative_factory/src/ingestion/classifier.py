"""
LLM-based material classification system for the Narrative Factory.

This module implements intelligent material classification using multiple LLM providers,
genre-aware prompting, progressive disclosure analysis, and dynamic category management.
"""

import asyncio
import os
import time
import uuid
from datetime import datetime
from typing import Any, Optional


try:
    from google import genai  # type: ignore
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from src.config import config
from src.exceptions import BusinessLogicError
from src.logger import get_logger
from src.models.material_models import (
    CategoryManager,
    MaterialClassification,
    MaterialIngestionRequest,
    MaterialIngestionResponse,
)


logger = get_logger(__name__)


class ClassificationPrompts:
    """Genre-aware prompt templates for material classification."""

    BASE_SYSTEM_PROMPT = """You are an expert material classifier for narrative content analysis.
Your task is to analyze story materials and classify them into appropriate categories based on genre context.

CORE PRINCIPLES:
1. Accuracy: Categorize materials precisely based on their actual content
2. Context Awareness: Consider genre-specific category requirements
3. Confidence: Provide realistic confidence scores (0.0-1.0)
4. Progressive Disclosure: Adapt analysis depth to material complexity

OUTPUT FORMAT: Always respond with valid JSON matching the required schema."""

    @staticmethod
    def get_classification_prompt(
        material: str,
        available_categories: list[str],
        genre_context: str,
        complexity_level: str = "medium"
    ) -> str:
        """Generate genre-aware classification prompt."""

        complexity_instructions = {
            "simple": "Focus on primary category identification with basic confidence scoring.",
            "medium": "Perform multi-category analysis with entity extraction and relationship mapping.",
            "complex": "Conduct comprehensive analysis including advanced metadata, cross-references, and detailed content mapping."
        }

        return f"""{ClassificationPrompts.BASE_SYSTEM_PROMPT}

**CLASSIFICATION CONTEXT:**
- Genre: {genre_context}
- Available Categories: {', '.join(available_categories)}
- Complexity Level: {complexity_level}
- Analysis Depth: {complexity_instructions.get(complexity_level, complexity_instructions['medium'])}

**MATERIAL TO CLASSIFY:**
{material[:2000]}{'...' if len(material) > 2000 else ''}

**GENRE-SPECIFIC GUIDANCE:**
{ClassificationPrompts._get_genre_guidance(genre_context)}

**REQUIRED OUTPUT:**
Analyze this material and provide a JSON response with the following structure:
{{
    "primary_category": "string (from available categories)",
    "secondary_categories": ["array of applicable secondary categories"],
    "category_confidence": {{
        "category_name": 0.0-1.0
    }},
    "extracted_entities": ["list of key entities/names/concepts"],
    "content_analysis": {{
        "key_themes": ["identified themes"],
        "narrative_elements": ["plot devices, character types, etc"],
        "temporal_scope": "past",  // Single value: past, present, future, or timeless
        "spoiler_risk": "low"  // Single value: low, medium, or high
    }},
    "complexity_indicators": {{
        "requires_advanced_analysis": true/false,
        "cross_reference_potential": true/false,
        "relationship_complexity": "simple|medium|complex"
    }},
    "processing_recommendations": {{
        "batch_priority": "low|normal|high|critical",
        "requires_manual_review": true/false
    }}
}}

**CLASSIFICATION REQUIREMENTS:**
1. Primary category must be from the available categories list
2. Confidence scores must be between 0.0 and 1.0
3. Focus on {complexity_level} complexity analysis
4. Consider genre-specific patterns for {genre_context}
5. Extract relevant entities and concepts
6. Assess spoiler risk and temporal context"""

    @staticmethod
    def _get_genre_guidance(genre: str) -> str:
        """
        Generate dynamic genre-specific classification guidance.
        
        Uses the LibrarianAgent's inherent cognitive abilities for genre analysis
        rather than constraining to hardcoded categories.
        """
        
        # Simplified cognitive approach that maintains dynamic analysis while ensuring JSON output
        return f"""DYNAMIC GENRE ANALYSIS for {genre}:
Apply cognitive analysis specific to {genre} storytelling patterns. Consider genre-unique elements like game mechanics (LitRPG), galactic scope (Space Opera), moral frameworks (Grimdark), or cozy atmosphere (Cozy Mystery). Adapt classification to serve {genre}-specific narrative functions and reader expectations.

CRITICAL: Respond ONLY with the required JSON object. No explanatory text before or after."""

    @staticmethod
    def get_batch_analysis_prompt(
        materials: list[str],
        available_categories: list[str],
        genre_context: str
    ) -> str:
        """Generate prompt for batch material analysis."""

        materials_text = ""
        for i, material in enumerate(materials[:10], 1):  # Limit to 10 for prompt size
            materials_text += f"\n**MATERIAL {i}:**\n{material[:500]}{'...' if len(material) > 500 else ''}\n"

        return f"""{ClassificationPrompts.BASE_SYSTEM_PROMPT}

**BATCH CLASSIFICATION TASK:**
Analyze the following {len(materials)} materials and classify each one.

**CONTEXT:**
- Genre: {genre_context}
- Available Categories: {', '.join(available_categories)}

**MATERIALS TO ANALYZE:**
{materials_text}

**REQUIRED OUTPUT:**
Provide a JSON array with one classification object per material:
[
    {{
        "material_index": 1,
        "primary_category": "string",
        "secondary_categories": ["array"],
        "category_confidence": {{"category": 0.0-1.0}},
        "extracted_entities": ["entities"],
        "processing_priority": "low|normal|high|critical"
    }},
    ...
]

**BATCH PROCESSING GUIDELINES:**
1. Maintain consistency across similar materials
2. Use comparative analysis to refine classifications
3. Identify potential cross-references between materials
4. Optimize processing order by complexity and relationships"""


class MaterialClassifier:
    """
    LLM-based material classifier with genre awareness and progressive disclosure.

    Supports multiple LLM providers (OpenAI, Gemini) with intelligent fallback,
    batch processing optimization, and dynamic category management.
    """

    def __init__(
        self,
        client_type: str = "gemini",
        fallback_client: Optional[str] = None,
        batch_size: int = 5,
        max_retries: int = 3
    ):
        """
        Initialize the material classifier.

        Args:
            client_type: Primary LLM client ("openai" or "gemini")
            fallback_client: Fallback client if primary fails
            batch_size: Default batch size for processing
            max_retries: Maximum retry attempts for failed classifications
        """
        self.client_type = client_type
        self.fallback_client = fallback_client
        self.batch_size = batch_size
        self.max_retries = max_retries

        # Initialize clients
        self.primary_client = None
        self.fallback_client_instance = None
        self._initialize_clients()

        # Processing state
        self._processing_stats = {
            "total_processed": 0,
            "successful_classifications": 0,
            "failed_classifications": 0,
            "average_confidence": 0.0,
            "processing_time": 0.0
        }

        logger.info(f"MaterialClassifier initialized with {client_type} client")

    def _initialize_clients(self) -> None:
        """Initialize LLM clients with proper configuration."""
        try:
            # Initialize primary client
            if self.client_type == "gemini":
                if not GENAI_AVAILABLE:
                    raise ImportError("google.genai not available")

                api_key = config.models.gemini_api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
                if api_key:
                    self.primary_client = genai.Client(api_key=api_key)
                else:
                    self.primary_client = genai.Client()

            elif self.client_type == "openai":
                if not OPENAI_AVAILABLE:
                    raise ImportError("openai not available")

                api_key = config.models.openai_api_key or os.getenv("OPENAI_API_KEY")
                if not api_key:
                    raise ValueError("OpenAI API key required")

                self.primary_client = OpenAI(api_key=api_key)
            else:
                raise ValueError(f"Unsupported client type: {self.client_type}")

            # Initialize fallback client if specified
            if self.fallback_client and self.fallback_client != self.client_type:
                try:
                    if self.fallback_client == "gemini" and GENAI_AVAILABLE:
                        api_key = config.models.gemini_api_key or os.getenv("GEMINI_API_KEY")
                        if api_key:
                            self.fallback_client_instance = genai.Client(api_key=api_key)
                    elif self.fallback_client == "openai" and OPENAI_AVAILABLE:
                        api_key = config.models.openai_api_key or os.getenv("OPENAI_API_KEY")
                        if api_key:
                            self.fallback_client_instance = OpenAI(api_key=api_key)
                except Exception as e:
                    logger.warning(f"Failed to initialize fallback client {self.fallback_client}: {e}")

        except Exception as e:
            logger.error(f"Failed to initialize {self.client_type} client: {e}")
            raise BusinessLogicError(f"Client initialization failed: {e}") from e

    async def classify_material(
        self,
        material: str,
        genre_context: str,
        additional_genres: Optional[list[str]] = None,
        custom_categories: Optional[list[str]] = None,
        complexity_level: Optional[str] = None
    ) -> MaterialClassification:
        """
        Classify a single material using LLM analysis.

        Args:
            material: Raw material content to classify
            genre_context: Primary genre for category selection
            additional_genres: Additional genres for multi-genre stories
            custom_categories: User-defined custom categories
            complexity_level: Force specific complexity level

        Returns:
            MaterialClassification with confidence scores and metadata
        """
        start_time = time.time()

        try:
            # Get available categories for this genre context
            all_genres = [genre_context] + (additional_genres or [])
            available_categories = CategoryManager.get_multi_genre_categories(all_genres)
            if custom_categories:
                available_categories.extend(custom_categories)
                available_categories = list(dict.fromkeys(available_categories))  # Remove duplicates

            # Determine complexity level if not specified
            if not complexity_level:
                complexity_level = self._assess_material_complexity(material, available_categories)

            # Generate classification prompt
            prompt = ClassificationPrompts.get_classification_prompt(
                material=material,
                available_categories=available_categories,
                genre_context=genre_context,
                complexity_level=complexity_level
            )

            # Get LLM classification
            classification_data = await self._generate_classification(prompt)

            # Create MaterialClassification instance
            material_classification = self._build_classification(
                material=material,
                classification_data=classification_data,
                genre_context=genre_context,
                additional_genres=additional_genres or [],
                available_categories=available_categories,
                complexity_level=complexity_level
            )

            # Update processing stats
            processing_time = time.time() - start_time
            self._update_stats(True, processing_time, classification_data.get("category_confidence", {}))

            logger.info(
                f"Material classified successfully: {material_classification.primary_category} "
                f"(confidence: {classification_data.get('category_confidence', {}).get(material_classification.primary_category, 0.0):.2f})"
            )

            return material_classification

        except Exception as e:
            processing_time = time.time() - start_time
            self._update_stats(False, processing_time, {})
            logger.error(f"Material classification failed: {e}")
            raise BusinessLogicError(f"Classification failed: {e}") from e

    async def classify_materials_batch(
        self,
        materials: list[str],
        genre_context: str,
        additional_genres: Optional[list[str]] = None,
        custom_categories: Optional[list[str]] = None,
        batch_size: Optional[int] = None
    ) -> list[MaterialClassification]:
        """
        Classify multiple materials in optimized batches.

        Args:
            materials: List of raw material content
            genre_context: Primary genre for category selection
            additional_genres: Additional genres for multi-genre stories
            custom_categories: User-defined custom categories
            batch_size: Override default batch size

        Returns:
            List of MaterialClassification instances
        """
        if not materials:
            return []

        batch_size = batch_size or self.batch_size
        classifications = []

        # Get available categories once for all materials
        all_genres = [genre_context] + (additional_genres or [])
        available_categories = CategoryManager.get_multi_genre_categories(all_genres)
        if custom_categories:
            available_categories.extend(custom_categories)
            available_categories = list(dict.fromkeys(available_categories))

        # Process in batches for efficiency
        for i in range(0, len(materials), batch_size):
            batch = materials[i:i + batch_size]

            try:
                # Use batch processing for efficiency when batch size > 1
                if len(batch) > 1:
                    batch_classifications = await self._classify_batch(
                        batch, available_categories, genre_context, additional_genres
                    )
                else:
                    # Single item - use individual classification
                    classification = await self.classify_material(
                        batch[0], genre_context, additional_genres, custom_categories
                    )
                    batch_classifications = [classification]

                classifications.extend(batch_classifications)

            except Exception as e:
                logger.error(f"Batch processing failed for materials {i}-{i+len(batch)}: {e}")

                # Fallback: process individually
                for material in batch:
                    try:
                        classification = await self.classify_material(
                            material, genre_context, additional_genres, custom_categories
                        )
                        classifications.append(classification)
                    except Exception as individual_error:
                        logger.error(f"Individual classification failed: {individual_error}")
                        # Create fallback classification
                        classifications.append(self._create_fallback_classification(
                            material, genre_context, available_categories
                        ))

        logger.info(f"Batch classification completed: {len(classifications)}/{len(materials)} successful")
        return classifications

    async def process_ingestion_request(
        self,
        request: MaterialIngestionRequest
    ) -> MaterialIngestionResponse:
        """
        Process a complete material ingestion request.

        Args:
            request: MaterialIngestionRequest with all processing parameters

        Returns:
            MaterialIngestionResponse with results and metrics
        """
        start_time = time.time()
        job_id = f"classification_{uuid.uuid4().hex[:8]}"

        try:
            logger.info(f"Starting ingestion job {job_id} with {len(request.materials)} materials")

            # Classify all materials
            classifications = await self.classify_materials_batch(
                materials=request.materials,
                genre_context=request.genre_context,
                additional_genres=request.additional_genres,
                custom_categories=request.custom_categories,
                batch_size=request.batch_size
            )

            # Filter by confidence threshold
            valid_classifications = [
                c for c in classifications
                if self._get_primary_confidence(c) >= request.min_confidence_threshold
            ]

            # Generate cross-references if enabled
            if request.enable_cross_references:
                self._generate_cross_references(valid_classifications)

            # Calculate metrics
            processing_time = time.time() - start_time
            cost_estimate = self._calculate_cost_estimate(len(request.materials), processing_time)

            response = MaterialIngestionResponse(
                job_id=job_id,
                status="completed" if valid_classifications else "partial",
                classifications=valid_classifications,
                failed_materials=[
                    {"material": mat, "error": "Below confidence threshold"}
                    for i, mat in enumerate(request.materials)
                    if i >= len(classifications) or
                    self._get_primary_confidence(classifications[i]) < request.min_confidence_threshold
                ],
                processing_time=processing_time,
                cost_estimate=cost_estimate,
                materials_processed=len(valid_classifications),
                average_confidence=self._calculate_average_confidence(valid_classifications),
                category_distribution=self._calculate_category_distribution(valid_classifications),
                complexity_distribution=self._calculate_complexity_distribution(valid_classifications),
                cross_references_identified=sum(
                    len(c.cross_references or {}) for c in valid_classifications
                ),
                completed_at=datetime.utcnow(),
                embedding_cache_hits=0  # Default value for now
            )

            logger.info(f"Ingestion job {job_id} completed: {len(valid_classifications)} materials processed")
            return response

        except Exception as e:
            logger.error(f"Ingestion job {job_id} failed: {e}")
            return MaterialIngestionResponse(
                job_id=job_id,
                status="failed",
                processing_time=time.time() - start_time,
                cost_estimate=0.0,
                materials_processed=0,
                average_confidence=0.0,
                embedding_cache_hits=0,
                cross_references_identified=0,
                completed_at=datetime.utcnow(),
                errors=[str(e)]
            )

    async def _generate_classification(self, prompt: str) -> dict[str, Any]:
        """Generate classification using LLM with fallback support."""
        for attempt in range(self.max_retries):
            try:
                # Try primary client
                result = await self._call_llm(self.primary_client, self.client_type, prompt)
                if result:
                    return result

            except Exception as e:
                logger.warning(f"Primary client failed (attempt {attempt + 1}): {e}")

                # Try fallback client if available
                if self.fallback_client_instance:
                    try:
                        result = await self._call_llm(
                            self.fallback_client_instance,
                            self.fallback_client,
                            prompt
                        )
                        if result:
                            logger.info(f"Fallback client succeeded on attempt {attempt + 1}")
                            return result
                    except Exception as fallback_error:
                        logger.warning(f"Fallback client failed: {fallback_error}")

                if attempt == self.max_retries - 1:
                    raise

                # Enhanced retry logic with exponential backoff + jitter
                base_delay = 2 ** attempt
                jitter = base_delay * 0.1 * (0.5 - (time.time() % 1))
                retry_delay = min(base_delay + jitter, 60.0)  # Cap at 60 seconds

                logger.info(f"Retrying in {retry_delay:.2f}s (attempt {attempt + 1}/{self.max_retries})")
                await asyncio.sleep(retry_delay)

        raise BusinessLogicError("All classification attempts failed")

    async def _call_llm(self, client: Any, client_type: str, prompt: str) -> dict[str, Any]:
        """Call LLM with proper client handling."""
        try:
            if client_type == "gemini":
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                    config={
                        'temperature': 0.3,
                        'max_output_tokens': 2048,
                    }
                )
                # Note: Paid tier supports higher rate limits
                # Rate limit: 15 RPM free tier -> 1000 RPM paid tier
                response_text = str(response.text)

            elif client_type == "openai":
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": ClassificationPrompts.BASE_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=2048
                )
                response_text = response.choices[0].message.content or ""
            else:
                raise ValueError(f"Unsupported client type: {client_type}")

            # Parse JSON response with enhanced error handling
            import json
            import re

            # Multiple strategies for JSON extraction
            json_str = None
            
            # Strategy 1: Look for complete JSON object with proper braces
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                # Strategy 2: Look for JSON between code blocks or explicit delimiters
                code_block_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
                if code_block_match:
                    json_str = code_block_match.group(1)
                else:
                    # Strategy 3: Find the first complete JSON object
                    brace_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                    if brace_match:
                        json_str = brace_match.group(0)

            if json_str:
                try:
                    # Clean up potential formatting issues
                    json_str = json_str.strip()
                    # Remove potential trailing comma issues
                    json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
                    return json.loads(json_str)
                except json.JSONDecodeError as decode_error:
                    logger.error(f"JSON decode error: {decode_error}")
                    logger.error(f"Problematic JSON string: {json_str[:500]}...")
                    raise ValueError(f"Invalid JSON structure: {decode_error}") from decode_error
            else:
                logger.error(f"No JSON found in response: {response_text[:500]}...")
                raise ValueError("No valid JSON found in response")

        except Exception as e:
            logger.error(f"LLM call failed for {client_type}: {e}")
            raise

    async def _classify_batch(
        self,
        materials: list[str],
        available_categories: list[str],
        genre_context: str,
        additional_genres: Optional[list[str]] = None
    ) -> list[MaterialClassification]:
        """Classify a batch of materials efficiently."""
        try:
            # Generate batch prompt
            prompt = ClassificationPrompts.get_batch_analysis_prompt(
                materials, available_categories, genre_context
            )

            # Get batch classification
            batch_results = await self._generate_classification(prompt)

            # Convert to MaterialClassification instances
            classifications: list[MaterialClassification] = []
            if isinstance(batch_results, list):
                for i, result in enumerate(batch_results):
                    if i < len(materials):
                        classification = self._build_classification(
                            material=materials[i],
                            classification_data=result,
                            genre_context=genre_context,
                            additional_genres=additional_genres or [],
                            available_categories=available_categories,
                            complexity_level="medium"
                        )
                        classifications.append(classification)

            return classifications

        except Exception as e:
            logger.error(f"Batch classification failed: {e}")
            raise

    def _build_classification(
        self,
        material: str,
        classification_data: dict[str, Any],
        genre_context: str,
        additional_genres: list[str],
        available_categories: list[str],
        complexity_level: str
    ) -> MaterialClassification:
        """Build MaterialClassification from LLM response data."""
        try:
            # Generate material ID and content hash
            material_id = f"material_{uuid.uuid4().hex[:8]}"
            content_hash = MaterialClassification.generate_content_hash(material)

            # Extract classification data with defaults
            primary_category = classification_data.get("primary_category", "plot_element")
            secondary_categories = classification_data.get("secondary_categories", [])
            category_confidence = classification_data.get("category_confidence", {})

            # Ensure primary category is valid
            if primary_category not in available_categories:
                logger.warning(f"Invalid primary category {primary_category}, using fallback")
                primary_category = available_categories[0] if available_categories else "plot_element"

            # Extract entities and analysis
            extracted_entities = classification_data.get("extracted_entities", [])
            content_analysis = classification_data.get("content_analysis", {})

            # Build classification
            classification = MaterialClassification(
                material_id=material_id,
                content=material,  # Add missing content field
                primary_category=primary_category,
                secondary_categories=secondary_categories,
                category_confidence=category_confidence,
                genre_context=genre_context,
                additional_genres=additional_genres,
                available_categories=available_categories,
                classification_method="genre_extended",  # Add missing field
                complexity_level=complexity_level,  # type: ignore  # complexity_level is validated to be correct literal
                content_hash=content_hash,
                extracted_entities=extracted_entities,
                content_length=len(material),
                temporal_scope=content_analysis.get("temporal_scope", "timeless"),
                spoiler_risk=content_analysis.get("spoiler_risk", "low"),
                advanced_metadata=None,  # Add missing field
                relationship_mapping=None,  # Add missing field  
                cross_references=None,  # Add missing field
                embedding_vector=None,  # Add missing field
                processing_priority=classification_data.get("processing_recommendations", {}).get("batch_priority", "normal"),
                updated_at=None,  # Add missing field
                classification_version="1.0"  # Add missing field
            )

            # Update complexity level based on categories
            classification.update_complexity_level()

            return classification

        except Exception as e:
            logger.error(f"Failed to build classification: {e}")
            # Return fallback classification
            return self._create_fallback_classification(material, genre_context, available_categories)

    def _create_fallback_classification(
        self,
        material: str,
        genre_context: str,
        available_categories: list[str]
    ) -> MaterialClassification:
        """Create a fallback classification for failed materials."""
        material_id = f"fallback_{uuid.uuid4().hex[:8]}"
        content_hash = MaterialClassification.generate_content_hash(material)

        return MaterialClassification(
            material_id=material_id,
            content=material,  # Add missing content field
            primary_category=available_categories[0] if available_categories else "plot_element",
            secondary_categories=[],
            category_confidence={available_categories[0]: 0.5} if available_categories else {},
            genre_context=genre_context,
            additional_genres=[],
            available_categories=available_categories,
            classification_method="base_only",  # Add missing field
            complexity_level="medium",
            content_hash=content_hash,
            extracted_entities=[],
            content_length=len(material),
            spoiler_risk="low",  # Add missing field
            temporal_scope="timeless",  # Add missing field
            advanced_metadata=None,  # Add missing field
            relationship_mapping=None,  # Add missing field
            cross_references=None,  # Add missing field
            embedding_vector=None,  # Add missing field
            processing_priority="low",
            updated_at=None,  # Add missing field
            classification_version="1.0"  # Add missing field
        )

    def _assess_material_complexity(self, material: str, available_categories: list[str]) -> str:
        """Assess complexity level of material for processing optimization."""
        # Simple heuristics for complexity assessment
        length = len(material)

        # Check for complex category indicators
        complex_indicators = [cat for cat in available_categories
                            if CategoryManager.get_complexity_level(cat) == "complex"]

        # Length-based assessment
        if length < 200:
            return "simple"
        elif length > 1000 or complex_indicators:
            return "complex"
        else:
            return "medium"

    def _generate_cross_references(self, classifications: list[MaterialClassification]) -> None:
        """Generate cross-references between classified materials."""
        # Simple entity-based cross-referencing
        entity_map: dict[str, list[str]] = {}

        # Build entity index
        for classification in classifications:
            for entity in classification.extracted_entities:
                if entity not in entity_map:
                    entity_map[entity] = []
                entity_map[entity].append(classification.material_id)

        # Add cross-references for shared entities
        for classification in classifications:
            for entity in classification.extracted_entities:
                related_materials = [mid for mid in entity_map[entity]
                                   if mid != classification.material_id]
                if related_materials:
                    for related_id in related_materials[:3]:  # Limit to 3 cross-refs
                        classification.add_cross_reference("shared_entity", related_id)

    def _get_primary_confidence(self, classification: MaterialClassification) -> float:
        """Get confidence score for primary category."""
        return classification.category_confidence.get(classification.primary_category, 0.0)

    def _calculate_average_confidence(self, classifications: list[MaterialClassification]) -> float:
        """Calculate average confidence across classifications."""
        if not classifications:
            return 0.0

        total_confidence = sum(self._get_primary_confidence(c) for c in classifications)
        return total_confidence / len(classifications)

    def _calculate_category_distribution(self, classifications: list[MaterialClassification]) -> dict[str, int]:
        """Calculate distribution of materials across categories."""
        distribution: dict[str, int] = {}
        for classification in classifications:
            category = classification.primary_category
            distribution[category] = distribution.get(category, 0) + 1
        return distribution

    def _calculate_complexity_distribution(self, classifications: list[MaterialClassification]) -> dict[str, int]:
        """Calculate distribution of materials across complexity levels."""
        distribution: dict[str, int] = {}
        for classification in classifications:
            level = classification.complexity_level
            distribution[level] = distribution.get(level, 0) + 1
        return distribution

    def _calculate_cost_estimate(self, material_count: int, processing_time: float) -> float:
        """Calculate rough cost estimate for processing."""
        # Simple cost estimation (tokens * rate)
        estimated_tokens = material_count * 1000  # Rough estimate
        cost_per_1k_tokens = 0.01  # Approximate cost
        return (estimated_tokens / 1000) * cost_per_1k_tokens

    def _update_stats(self, success: bool, processing_time: float, confidence_scores: dict[str, float]) -> None:
        """Update internal processing statistics."""
        self._processing_stats["total_processed"] += 1

        if success:
            self._processing_stats["successful_classifications"] += 1
            if confidence_scores:
                avg_confidence = sum(confidence_scores.values()) / len(confidence_scores)
                current_avg = self._processing_stats["average_confidence"]
                total_successful = self._processing_stats["successful_classifications"]
                self._processing_stats["average_confidence"] = (
                    (current_avg * (total_successful - 1) + avg_confidence) / total_successful
                )
        else:
            self._processing_stats["failed_classifications"] += 1

        self._processing_stats["processing_time"] += processing_time

    def get_processing_stats(self) -> dict[str, Any]:
        """Get current processing statistics."""
        return self._processing_stats.copy()

    async def health_check(self) -> dict[str, Any]:
        """Perform health check on classifier components."""
        health_status = {
            "classifier_ready": True,
            "primary_client": self.client_type,
            "fallback_available": self.fallback_client_instance is not None,
            "processing_stats": self.get_processing_stats(),
            "errors": []
        }

        # Test primary client
        try:
            if self.primary_client:
                await asyncio.wait_for(
                    self._call_llm(self.primary_client, self.client_type,
                                 "Respond with JSON: {'status': 'healthy'}"),
                    timeout=10.0
                )
            else:
                health_status["errors"].append("Primary client not initialized")
                health_status["classifier_ready"] = False
        except Exception as e:
            health_status["errors"].append(f"Primary client test failed: {e}")
            health_status["classifier_ready"] = False

        return health_status
