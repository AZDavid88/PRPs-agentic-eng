"""
Dynamic material classification models for the Narrative Factory ingestion pipeline.

This module implements a flexible, genre-aware classification system that adapts
to different story types while maintaining type safety and validation.
"""

from datetime import datetime
from hashlib import sha256
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, validator


# =============================================================================
# DYNAMIC CATEGORY SYSTEM
# =============================================================================

# Base categories present in all genres
BASE_CATEGORIES = [
    "character",       # Universal - every story has characters
    "setting",         # Universal - every story has locations/environments
    "narrative_style", # Universal - every story has voice/tone
    "plot_element"     # Universal - every story has events/conflicts
]

# Genre-specific category extensions
GENRE_EXTENSIONS = {
    "fantasy": [
        "magic_system", "world_building", "mythology", "creatures",
        "ancient_history", "prophecy", "artifact"
    ],
    "romance": [
        "relationship_dynamic", "emotional_beat", "romantic_tension",
        "intimacy_level", "character_chemistry", "romantic_arc"
    ],
    "mystery": [
        "clue", "evidence", "red_herring", "investigative_method",
        "suspect_profile", "crime_scene", "detective_reasoning"
    ],
    "thriller": [
        "tension_mechanism", "chase_element", "threat_profile",
        "action_sequence", "suspense_building", "danger_escalation"
    ],
    "sci_fi": [
        "technology", "scientific_principle", "future_society",
        "alien_culture", "space_travel", "technological_conflict"
    ],
    "historical": [
        "period_detail", "cultural_norm", "historical_event",
        "social_hierarchy", "period_language", "historical_accuracy"
    ],
    "horror": [
        "threat_entity", "fear_mechanism", "atmospheric_element",
        "psychological_horror", "supernatural_element", "survival_element"
    ],
    "adventure": [
        "journey_element", "obstacle", "discovery", "exploration",
        "physical_challenge", "quest_objective"
    ],
    "literary": [
        "symbolic_element", "thematic_device", "literary_technique",
        "character_psychology", "social_commentary", "philosophical_concept"
    ]
}

# Complexity indicators for processing optimization
COMPLEXITY_INDICATORS = {
    "simple": ["character", "setting", "plot_element"],
    "medium": ["narrative_style", "relationship_dynamic", "clue", "technology"],
    "complex": [
        "magic_system", "world_building", "mythology", "scientific_principle",
        "philosophical_concept", "social_commentary"
    ]
}


class CategoryManager:
    """Manages dynamic category systems per genre with validation and optimization."""

    @staticmethod
    def get_valid_categories(
        genre: str,
        custom_categories: Optional[list[str]] = None
    ) -> list[str]:
        """
        Return valid categories for a given genre plus any custom additions.

        Args:
            genre: Primary genre context
            custom_categories: Additional user-defined categories

        Returns:
            List of valid category names for this context
        """
        categories = BASE_CATEGORIES.copy()

        # Add genre-specific extensions
        genre_extensions = GENRE_EXTENSIONS.get(genre.lower(), [])
        categories.extend(genre_extensions)

        # Add custom categories if provided
        if custom_categories:
            categories.extend(custom_categories)

        # Remove duplicates while preserving order
        return list(dict.fromkeys(categories))

    @staticmethod
    def get_complexity_level(category: str) -> str:
        """Determine processing complexity level for a category."""
        for level, cats in COMPLEXITY_INDICATORS.items():
            if category in cats:
                return level
        return "medium"  # Default for unknown categories

    @staticmethod
    def validate_categories(
        categories: list[str],
        genre: str,
        custom_categories: Optional[list[str]] = None
    ) -> bool:
        """Validate that all categories are valid for the given context."""
        valid_categories = set(
            CategoryManager.get_valid_categories(genre, custom_categories)
        )
        return all(cat in valid_categories for cat in categories)

    @staticmethod
    def get_multi_genre_categories(genres: list[str]) -> list[str]:
        """Get union of categories for multi-genre stories."""
        all_categories = set(BASE_CATEGORIES)

        for genre in genres:
            genre_extensions = GENRE_EXTENSIONS.get(genre.lower(), [])
            all_categories.update(genre_extensions)

        return list(all_categories)


# =============================================================================
# CORE DATA MODELS
# =============================================================================

class MaterialClassification(BaseModel):
    """
    Dynamic classification model supporting genre-specific categories.

    This model adapts to different story genres while maintaining validation
    and type safety for material ingestion processing.
    """

    # Core identification
    material_id: str = Field(..., description="Unique identifier for this material")

    # DYNAMIC CLASSIFICATION SYSTEM
    primary_category: str = Field(
        ...,
        description="Primary material category from available set"
    )
    secondary_categories: list[str] = Field(
        default_factory=list,
        description="Additional applicable categories (multi-classification)"
    )
    category_confidence: dict[str, float] = Field(
        default_factory=dict,
        description="Confidence scores (0.0-1.0) for each category assignment"
    )

    # Genre and context information
    genre_context: str = Field(
        ...,
        description="Primary genre context for category validation"
    )
    additional_genres: list[str] = Field(
        default_factory=list,
        description="Additional genres for multi-genre stories"
    )
    available_categories: list[str] = Field(
        default_factory=list,
        description="Valid categories for this genre/story context"
    )

    # Classification metadata
    classification_method: Literal["base_only", "genre_extended", "multi_genre", "custom"] = Field(
        "genre_extended",
        description="Classification approach used"
    )
    complexity_level: Literal["simple", "medium", "complex"] = Field(
        "medium",
        description="Processing complexity indicator for optimization"
    )

    # Content and processing metadata
    content_hash: str = Field(..., description="SHA256 hash of original content")
    extracted_entities: list[str] = Field(
        default_factory=list,
        description="Named entities extracted from content"
    )
    content_length: int = Field(0, description="Character count of original content")

    # Temporal gating (spoiler prevention)
    chapter_availability: dict[str, int] = Field(
        default_factory=dict,
        description="Earliest chapter number for availability by story thread"
    )
    spoiler_risk: Literal["low", "medium", "high"] = Field(
        "low",
        description="Risk of containing story spoilers"
    )
    temporal_scope: Literal["past", "present", "future", "timeless"] = Field(
        "timeless",
        description="Temporal context of material content"
    )

    # Progressive disclosure fields (populated based on complexity)
    advanced_metadata: Optional[dict[str, Any]] = Field(
        None,
        description="Advanced metadata for complex materials"
    )
    relationship_mapping: Optional[list[str]] = Field(
        None,
        description="IDs of related materials"
    )
    cross_references: Optional[dict[str, list[str]]] = Field(
        None,
        description="References to other materials by category"
    )

    # Processing optimization
    embedding_vector: Optional[list[float]] = Field(
        None,
        description="Cached embedding vector (2048-dim for Jina v4)"
    )
    processing_priority: Literal["low", "normal", "high", "critical"] = Field(
        "normal",
        description="Processing priority for pipeline optimization"
    )

    # Timestamps and versioning
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Material creation timestamp"
    )
    updated_at: Optional[datetime] = Field(
        None,
        description="Last update timestamp"
    )
    classification_version: str = Field(
        "1.0",
        description="Classification schema version for migration"
    )

    # Validation methods
    @validator('primary_category')
    def validate_primary_category(cls, v, values):
        """Ensure primary category is valid for the genre context."""
        genre = values.get('genre_context')
        additional_genres = values.get('additional_genres', [])

        if genre:
            all_genres = [genre] + additional_genres
            valid_categories = CategoryManager.get_multi_genre_categories(all_genres)

            if v not in valid_categories:
                raise ValueError(
                    f"Category '{v}' not valid for genre(s) {all_genres}. "
                    f"Valid categories: {valid_categories}"
                )
        return v

    @validator('secondary_categories')
    def validate_secondary_categories(cls, v, values):
        """Ensure all secondary categories are valid."""
        genre = values.get('genre_context')
        additional_genres = values.get('additional_genres', [])

        if genre and v:
            all_genres = [genre] + additional_genres
            valid_categories = set(CategoryManager.get_multi_genre_categories(all_genres))

            invalid_categories = [cat for cat in v if cat not in valid_categories]
            if invalid_categories:
                raise ValueError(
                    f"Invalid secondary categories: {invalid_categories}. "
                    f"Valid categories: {list(valid_categories)}"
                )
        return v

    @validator('category_confidence')
    def validate_confidence_scores(cls, v):
        """Ensure confidence scores are between 0.0 and 1.0."""
        invalid_scores = {k: score for k, score in v.items()
                         if not (0.0 <= score <= 1.0)}
        if invalid_scores:
            raise ValueError(f"Confidence scores must be 0.0-1.0: {invalid_scores}")
        return v

    @validator('content_hash')
    def validate_content_hash(cls, v):
        """Ensure content hash is valid SHA256."""
        if len(v) != 64 or not all(c in '0123456789abcdef' for c in v.lower()):
            raise ValueError("content_hash must be a valid SHA256 hex string")
        return v.lower()

    def update_complexity_level(self) -> None:
        """Update complexity level based on assigned categories."""
        all_categories = [self.primary_category] + self.secondary_categories
        max_complexity = "simple"

        for category in all_categories:
            cat_complexity = CategoryManager.get_complexity_level(category)
            if cat_complexity == "complex":
                max_complexity = "complex"
                break
            elif cat_complexity == "medium" and max_complexity == "simple":
                max_complexity = "medium"

        self.complexity_level = max_complexity

    def add_cross_reference(self, category: str, material_id: str) -> None:
        """Add a cross-reference to another material."""
        if self.cross_references is None:
            self.cross_references = {}

        if category not in self.cross_references:
            self.cross_references[category] = []

        if material_id not in self.cross_references[category]:
            self.cross_references[category].append(material_id)

    @classmethod
    def generate_content_hash(cls, content: str) -> str:
        """Generate SHA256 hash for content."""
        return sha256(content.encode('utf-8')).hexdigest()


class MaterialIngestionRequest(BaseModel):
    """Request model for dynamic material ingestion."""

    # Core request data
    materials: list[str] = Field(
        ...,
        description="Raw material content to be classified"
    )

    # Genre and classification context
    genre_context: str = Field(
        "unknown",
        description="Primary genre context for classification"
    )
    additional_genres: list[str] = Field(
        default_factory=list,
        description="Additional genres for multi-genre stories"
    )
    custom_categories: Optional[list[str]] = Field(
        None,
        description="User-defined custom categories for this story"
    )

    # Processing configuration
    processing_mode: Literal["pipeline", "agent", "hybrid"] = Field(
        "pipeline",
        description="Processing approach (pipeline=fast, agent=comprehensive)"
    )
    batch_size: int = Field(
        10,
        description="Batch size for processing optimization",
        ge=1, le=100
    )
    enable_cross_references: bool = Field(
        True,
        description="Whether to identify cross-references between materials"
    )

    # Quality and optimization settings
    min_confidence_threshold: float = Field(
        0.7,
        description="Minimum confidence score for category assignment",
        ge=0.0, le=1.0
    )
    enable_progressive_disclosure: bool = Field(
        True,
        description="Whether to enable progressive complexity analysis"
    )

    # Metadata
    story_id: Optional[str] = Field(
        None,
        description="Associated story identifier"
    )
    user_id: Optional[str] = Field(
        None,
        description="User identifier for tracking"
    )


class MaterialIngestionResponse(BaseModel):
    """Response model for material ingestion with comprehensive results."""

    # Processing results
    job_id: str = Field(..., description="Processing job identifier")
    status: Literal["processing", "completed", "failed", "partial"] = Field(
        ...,
        description="Processing status"
    )

    # Classification results
    classifications: list[MaterialClassification] = Field(
        default_factory=list,
        description="Completed material classifications"
    )
    failed_materials: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Materials that failed classification with error details"
    )

    # Processing metadata
    processing_time: float = Field(
        ...,
        description="Total processing time in seconds"
    )
    cost_estimate: float = Field(
        ...,
        description="Processing cost estimate in USD"
    )
    materials_processed: int = Field(
        0,
        description="Number of materials successfully processed"
    )

    # Quality metrics
    average_confidence: float = Field(
        0.0,
        description="Average confidence score across all classifications"
    )
    category_distribution: dict[str, int] = Field(
        default_factory=dict,
        description="Count of materials per category"
    )
    complexity_distribution: dict[str, int] = Field(
        default_factory=dict,
        description="Count of materials per complexity level"
    )

    # System metrics
    embedding_cache_hits: int = Field(
        0,
        description="Number of embedding cache hits for optimization"
    )
    cross_references_identified: int = Field(
        0,
        description="Number of cross-references identified"
    )

    # Error handling
    errors: list[str] = Field(
        default_factory=list,
        description="Processing errors and warnings"
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Non-fatal processing warnings"
    )

    # Timestamps
    started_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Processing start timestamp"
    )
    completed_at: Optional[datetime] = Field(
        None,
        description="Processing completion timestamp"
    )


class MaterialQueryRequest(BaseModel):
    """Request model for querying classified materials."""

    # Query parameters
    categories: Optional[list[str]] = Field(
        None,
        description="Filter by specific categories"
    )
    genre_context: Optional[str] = Field(
        None,
        description="Filter by genre context"
    )
    complexity_levels: Optional[list[str]] = Field(
        None,
        description="Filter by complexity levels"
    )
    spoiler_risk: Optional[list[str]] = Field(
        None,
        description="Filter by spoiler risk levels"
    )

    # Temporal filtering
    max_chapter: Optional[int] = Field(
        None,
        description="Maximum chapter number for spoiler prevention"
    )
    temporal_scope: Optional[list[str]] = Field(
        None,
        description="Filter by temporal scope"
    )

    # Search and similarity
    similarity_query: Optional[str] = Field(
        None,
        description="Text query for semantic similarity search"
    )
    min_similarity_score: float = Field(
        0.7,
        description="Minimum similarity score for results",
        ge=0.0, le=1.0
    )

    # Result configuration
    limit: int = Field(
        50,
        description="Maximum number of results to return",
        ge=1, le=1000
    )
    include_cross_references: bool = Field(
        False,
        description="Whether to include cross-referenced materials"
    )


class MaterialQueryResponse(BaseModel):
    """Response model for material queries."""

    # Results
    materials: list[MaterialClassification] = Field(
        default_factory=list,
        description="Matching materials"
    )
    total_count: int = Field(
        0,
        description="Total number of matching materials"
    )

    # Query metadata
    query_time: float = Field(
        ...,
        description="Query execution time in seconds"
    )
    filters_applied: dict[str, Any] = Field(
        default_factory=dict,
        description="Summary of applied filters"
    )

    # Cross-reference data
    cross_references: Optional[dict[str, list[MaterialClassification]]] = Field(
        None,
        description="Cross-referenced materials by category"
    )
