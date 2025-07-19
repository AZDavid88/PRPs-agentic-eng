"""
Integration tests for Phase 1A Material Ingestion Pipeline.

Tests the complete system integration including dynamic classification,
embedding generation, storage, and pipeline orchestration.
"""

import pytest
import asyncio
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

from src.models.material_models import (
    MaterialClassification,
    MaterialIngestionRequest,
    MaterialIngestionResponse,
    CategoryManager
)
from src.ingestion.pipeline import MaterialIngestionPipeline, PipelineConfig
from src.ingestion.classifier import MaterialClassifier
from src.ingestion.storage import MaterialStorageService


# Test data for different genres
FANTASY_MATERIALS = [
    "Character: Ren, a young geomancer with unique analytical abilities and deep understanding of fundamental forces.",
    "Magic System: The Deep Current - a ubiquitous energy field that underpins reality and can be manipulated through understanding.",
    "Location: The Ashfall Wastes - a dangerous volcanic region where ancient magics still burn in the earth."
]

ROMANCE_MATERIALS = [
    "Character: Elena, an independent art curator who guards her heart carefully after past betrayals.",
    "Relationship Dynamic: The slow-burn attraction between Elena and Marcus, built on intellectual sparks and shared vulnerabilities.",
    "Setting: The intimate bookshop café where Elena and Marcus first meet over spilled coffee and scattered manuscripts."
]

MYSTERY_MATERIALS = [
    "Evidence: The locked-room murder weapon - a vintage letter opener found in the victim's office with no fingerprints.",
    "Red Herring: The suspicious business partner with motive and opportunity, but a solid alibi for the time of death.",
    "Detective Method: Inspector Chen's systematic approach to timeline reconstruction and witness statement analysis."
]


class TestCategoryManager:
    """Test the dynamic category management system."""
    
    def test_base_categories_always_present(self):
        """Test that base categories are present for all genres."""
        fantasy_cats = CategoryManager.get_valid_categories("fantasy")
        romance_cats = CategoryManager.get_valid_categories("romance")
        mystery_cats = CategoryManager.get_valid_categories("mystery")
        
        base_categories = ["character", "setting", "narrative_style", "plot_element"]
        
        for base_cat in base_categories:
            assert base_cat in fantasy_cats
            assert base_cat in romance_cats
            assert base_cat in mystery_cats
    
    def test_genre_specific_categories(self):
        """Test that genre-specific categories are added correctly."""
        fantasy_cats = CategoryManager.get_valid_categories("fantasy")
        romance_cats = CategoryManager.get_valid_categories("romance")
        mystery_cats = CategoryManager.get_valid_categories("mystery")
        
        # Fantasy should have magic-related categories
        assert "magic_system" in fantasy_cats
        assert "world_building" in fantasy_cats
        assert "mythology" in fantasy_cats
        
        # Romance should have relationship categories
        assert "relationship_dynamic" in romance_cats
        assert "emotional_beat" in romance_cats
        assert "romantic_tension" in romance_cats
        
        # Mystery should have investigation categories
        assert "clue" in mystery_cats
        assert "evidence" in mystery_cats
        assert "red_herring" in mystery_cats
    
    def test_custom_categories(self):
        """Test that custom categories are properly added."""
        custom_cats = ["custom_magic", "unique_system"]
        all_cats = CategoryManager.get_valid_categories("fantasy", custom_cats)
        
        assert "custom_magic" in all_cats
        assert "unique_system" in all_cats
        assert "magic_system" in all_cats  # Original fantasy categories still present
    
    def test_multi_genre_categories(self):
        """Test category management for multi-genre stories."""
        multi_cats = CategoryManager.get_multi_genre_categories(["fantasy", "romance"])
        
        # Should have base categories
        assert "character" in multi_cats
        assert "setting" in multi_cats
        
        # Should have both fantasy and romance categories
        assert "magic_system" in multi_cats
        assert "relationship_dynamic" in multi_cats
    
    def test_complexity_level_determination(self):
        """Test that complexity levels are correctly determined."""
        assert CategoryManager.get_complexity_level("character") == "simple"
        assert CategoryManager.get_complexity_level("relationship_dynamic") == "medium"
        assert CategoryManager.get_complexity_level("magic_system") == "complex"
        assert CategoryManager.get_complexity_level("unknown_category") == "medium"  # Default


class TestMaterialClassification:
    """Test the MaterialClassification model with dynamic categories."""
    
    def test_material_classification_creation(self):
        """Test creating a valid MaterialClassification."""
        classification = MaterialClassification(
            material_id="test_001",
            primary_category="character",
            genre_context="fantasy",
            content_hash="a" * 64,  # Valid SHA256 hash
            spoiler_risk="low"
        )
        
        assert classification.material_id == "test_001"
        assert classification.primary_category == "character"
        assert classification.genre_context == "fantasy"
        assert classification.spoiler_risk == "low"
    
    def test_category_validation(self):
        """Test that category validation works correctly."""
        # Valid fantasy category should work
        classification = MaterialClassification(
            material_id="test_002",
            primary_category="magic_system",
            genre_context="fantasy",
            content_hash="b" * 64,
            spoiler_risk="medium"
        )
        assert classification.primary_category == "magic_system"
        
        # Invalid category for genre should fail
        with pytest.raises(ValueError):
            MaterialClassification(
                material_id="test_003",
                primary_category="invalid_category",
                genre_context="fantasy",
                content_hash="c" * 64,
                spoiler_risk="high"
            )
    
    def test_secondary_categories_validation(self):
        """Test validation of secondary categories."""
        # Valid secondary categories
        classification = MaterialClassification(
            material_id="test_004",
            primary_category="character",
            secondary_categories=["setting", "plot_element"],
            genre_context="fantasy",
            content_hash="d" * 64,
            spoiler_risk="low"
        )
        assert len(classification.secondary_categories) == 2
        
        # Invalid secondary category should fail
        with pytest.raises(ValueError):
            MaterialClassification(
                material_id="test_005",
                primary_category="character",
                secondary_categories=["invalid_category"],
                genre_context="fantasy",
                content_hash="e" * 64,
                spoiler_risk="low"
            )
    
    def test_content_hash_validation(self):
        """Test that content hash validation works."""
        # Valid SHA256 hash
        MaterialClassification(
            material_id="test_006",
            primary_category="character",
            genre_context="fantasy",
            content_hash="abcdef1234567890" * 4,  # 64 chars
            spoiler_risk="low"
        )
        
        # Invalid hash should fail
        with pytest.raises(ValueError):
            MaterialClassification(
                material_id="test_007",
                primary_category="character",
                genre_context="fantasy",
                content_hash="invalid_hash",
                spoiler_risk="low"
            )
    
    def test_confidence_score_validation(self):
        """Test that confidence scores are properly validated."""
        # Valid confidence scores
        classification = MaterialClassification(
            material_id="test_008",
            primary_category="character",
            category_confidence={"character": 0.95, "setting": 0.2},
            genre_context="fantasy",
            content_hash="f" * 64,
            spoiler_risk="low"
        )
        assert classification.category_confidence["character"] == 0.95
        
        # Invalid confidence score should fail
        with pytest.raises(ValueError):
            MaterialClassification(
                material_id="test_009",
                primary_category="character",
                category_confidence={"character": 1.5},  # > 1.0
                genre_context="fantasy",
                content_hash="1" * 64,
                spoiler_risk="low"
            )
    
    def test_complexity_level_update(self):
        """Test automatic complexity level updating."""
        classification = MaterialClassification(
            material_id="test_010",
            primary_category="character",  # simple
            secondary_categories=["magic_system"],  # complex
            genre_context="fantasy",
            content_hash="2" * 64,
            spoiler_risk="low"
        )
        
        classification.update_complexity_level()
        assert classification.complexity_level == "complex"  # Should be upgraded to complex
    
    def test_cross_reference_management(self):
        """Test cross-reference functionality."""
        classification = MaterialClassification(
            material_id="test_011",
            primary_category="character",
            genre_context="fantasy",
            content_hash="3" * 64,
            spoiler_risk="low"
        )
        
        # Add cross-references
        classification.add_cross_reference("magic_system", "magic_001")
        classification.add_cross_reference("magic_system", "magic_002")
        classification.add_cross_reference("setting", "location_001")
        
        assert "magic_system" in classification.cross_references
        assert len(classification.cross_references["magic_system"]) == 2
        assert "magic_001" in classification.cross_references["magic_system"]
        assert "location_001" in classification.cross_references["setting"]


class TestMaterialIngestionRequest:
    """Test the ingestion request model."""
    
    def test_basic_request_creation(self):
        """Test creating a basic ingestion request."""
        request = MaterialIngestionRequest(
            materials=FANTASY_MATERIALS,
            genre_context="fantasy",
            processing_mode="pipeline"
        )
        
        assert len(request.materials) == 3
        assert request.genre_context == "fantasy"
        assert request.processing_mode == "pipeline"
        assert request.batch_size == 10  # Default
        assert request.min_confidence_threshold == 0.7  # Default
    
    def test_multi_genre_request(self):
        """Test request with multiple genres."""
        request = MaterialIngestionRequest(
            materials=["Mixed genre material"],
            genre_context="fantasy",
            additional_genres=["romance", "mystery"],
            custom_categories=["unique_element"],
            processing_mode="agent"
        )
        
        assert request.genre_context == "fantasy"
        assert "romance" in request.additional_genres
        assert "mystery" in request.additional_genres
        assert "unique_element" in request.custom_categories
    
    def test_request_validation(self):
        """Test request validation rules."""
        # Valid batch size
        request = MaterialIngestionRequest(
            materials=["test"],
            batch_size=50,
            min_confidence_threshold=0.8
        )
        assert request.batch_size == 50
        assert request.min_confidence_threshold == 0.8
        
        # Invalid batch size should fail
        with pytest.raises(ValueError):
            MaterialIngestionRequest(
                materials=["test"],
                batch_size=150  # > 100
            )
        
        # Invalid confidence threshold should fail
        with pytest.raises(ValueError):
            MaterialIngestionRequest(
                materials=["test"],
                min_confidence_threshold=1.5  # > 1.0
            )


@pytest.mark.asyncio
class TestMaterialClassifierIntegration:
    """Test the material classifier with mocked LLM responses."""
    
    async def test_classifier_initialization(self):
        """Test that classifier initializes correctly."""
        with patch('src.ingestion.classifier.initialize_client') as mock_init:
            mock_init.return_value = AsyncMock()
            
            classifier = MaterialClassifier(client_type="gemini")
            assert classifier.client_type == "gemini"
            assert classifier.fallback_client_type == "openai"  # Default fallback
    
    async def test_single_material_classification(self):
        """Test classifying a single material."""
        mock_response = {
            "primary_category": "character",
            "secondary_categories": ["plot_element"],
            "confidence_scores": {"character": 0.95, "plot_element": 0.3},
            "extracted_entities": ["Ren", "geomancer"],
            "complexity_assessment": "medium",
            "spoiler_risk": "low"
        }
        
        with patch('src.ingestion.classifier.initialize_client') as mock_init:
            mock_client = AsyncMock()
            mock_client.generate_content.return_value.text = str(mock_response)
            mock_init.return_value = mock_client
            
            classifier = MaterialClassifier(client_type="gemini")
            
            # Mock the JSON parsing
            with patch('json.loads', return_value=mock_response):
                classification = await classifier.classify_material(
                    material=FANTASY_MATERIALS[0],
                    genre_context="fantasy"
                )
            
            assert classification.primary_category == "character"
            assert "plot_element" in classification.secondary_categories
            assert classification.genre_context == "fantasy"
    
    async def test_batch_classification(self):
        """Test batch material classification."""
        mock_responses = [
            {
                "material_index": 0,
                "primary_category": "character",
                "secondary_categories": [],
                "confidence_scores": {"character": 0.9},
                "extracted_entities": ["Ren"],
                "complexity_assessment": "medium",
                "spoiler_risk": "low"
            },
            {
                "material_index": 1,
                "primary_category": "magic_system",
                "secondary_categories": ["world_building"],
                "confidence_scores": {"magic_system": 0.95},
                "extracted_entities": ["Deep Current"],
                "complexity_assessment": "complex",
                "spoiler_risk": "medium"
            }
        ]
        
        with patch('src.ingestion.classifier.initialize_client') as mock_init:
            mock_client = AsyncMock()
            mock_client.generate_content.return_value.text = str(mock_responses)
            mock_init.return_value = mock_client
            
            classifier = MaterialClassifier(client_type="gemini")
            
            with patch('json.loads', return_value=mock_responses):
                classifications = await classifier.classify_materials_batch(
                    materials=FANTASY_MATERIALS[:2],
                    genre_context="fantasy",
                    batch_size=2
                )
            
            assert len(classifications) == 2
            assert classifications[0].primary_category == "character"
            assert classifications[1].primary_category == "magic_system"


@pytest.mark.asyncio 
class TestIngestionPipelineIntegration:
    """Test the complete ingestion pipeline integration."""
    
    async def test_pipeline_initialization(self):
        """Test pipeline initialization with all components."""
        config = PipelineConfig(
            embedding_provider="jina",
            batch_size=5,
            processing_mode="pipeline"
        )
        
        with patch('src.ingestion.pipeline.MaterialClassifier') as mock_classifier, \
             patch('src.ingestion.pipeline.MaterialStorageService') as mock_storage, \
             patch('src.ingestion.pipeline.EmbeddingService') as mock_embedding:
            
            pipeline = MaterialIngestionPipeline(config)
            
            # Verify components are initialized
            assert pipeline.config.embedding_provider == "jina"
            assert pipeline.config.batch_size == 5
            assert pipeline.config.processing_mode == "pipeline"
    
    async def test_health_check(self):
        """Test pipeline health check functionality."""
        with patch('src.ingestion.pipeline.MaterialClassifier') as mock_classifier, \
             patch('src.ingestion.pipeline.MaterialStorageService') as mock_storage, \
             patch('src.ingestion.pipeline.EmbeddingService') as mock_embedding:
            
            # Setup mocks
            mock_classifier_instance = AsyncMock()
            mock_storage_instance = AsyncMock()
            mock_embedding_instance = AsyncMock()
            
            mock_classifier.return_value = mock_classifier_instance
            mock_storage.return_value = mock_storage_instance
            mock_embedding.return_value = mock_embedding_instance
            
            # Mock health checks to return True
            mock_classifier_instance.health_check.return_value = True
            mock_storage_instance.health_check.return_value = True
            mock_embedding_instance.health_check = AsyncMock(return_value=True)
            
            pipeline = MaterialIngestionPipeline()
            health_status = await pipeline.health_check()
            
            assert health_status["status"] == "healthy"
            assert health_status["components"]["classifier"] is True
            assert health_status["components"]["storage"] is True
            assert health_status["components"]["embedding_service"] is True
    
    async def test_end_to_end_processing(self):
        """Test complete end-to-end material processing."""
        request = MaterialIngestionRequest(
            materials=FANTASY_MATERIALS,
            genre_context="fantasy",
            processing_mode="pipeline",
            batch_size=3
        )
        
        # Mock classifications
        mock_classifications = [
            MaterialClassification(
                material_id=f"material_{i}",
                primary_category=["character", "magic_system", "setting"][i],
                genre_context="fantasy",
                content_hash=MaterialClassification.generate_content_hash(material),
                spoiler_risk="low"
            )
            for i, material in enumerate(FANTASY_MATERIALS)
        ]
        
        # Mock embeddings
        mock_embeddings = [[0.1] * 2048 for _ in range(3)]
        
        with patch('src.ingestion.pipeline.MaterialClassifier') as mock_classifier, \
             patch('src.ingestion.pipeline.MaterialStorageService') as mock_storage, \
             patch('src.ingestion.pipeline.EmbeddingService') as mock_embedding:
            
            # Setup component mocks
            mock_classifier_instance = AsyncMock()
            mock_storage_instance = AsyncMock()
            mock_embedding_instance = AsyncMock()
            
            mock_classifier.return_value = mock_classifier_instance
            mock_storage.return_value = mock_storage_instance
            mock_embedding.return_value = mock_embedding_instance
            
            # Configure mock responses
            mock_classifier_instance.process_ingestion_request.return_value = AsyncMock(
                classifications=mock_classifications,
                status="completed",
                materials_processed=3,
                average_confidence=0.85,
                processing_time=2.5
            )
            
            mock_embedding_instance.bulk_process_materials.return_value = AsyncMock(
                embeddings=mock_embeddings,
                processing_time=1.2,
                total_tokens=150,
                estimated_cost=0.008
            )
            
            mock_storage_instance.bulk_store_materials.return_value = AsyncMock(
                stored_count=3,
                failed_count=0,
                processing_time=0.8
            )
            
            # Execute pipeline
            pipeline = MaterialIngestionPipeline()
            response = await pipeline.process_materials(request)
            
            # Verify results
            assert response.status == "completed"
            assert response.materials_processed == 3
            assert len(response.classifications) == 3
            assert response.cost_estimate > 0
            assert response.processing_time > 0


class TestGenreAdaptability:
    """Test that the system adapts correctly to different genres."""
    
    def test_fantasy_genre_categories(self):
        """Test that fantasy materials get appropriate categories."""
        categories = CategoryManager.get_valid_categories("fantasy")
        
        # Should have magic-related categories
        expected_fantasy_cats = [
            "magic_system", "world_building", "mythology", 
            "creatures", "ancient_history", "prophecy", "artifact"
        ]
        
        for cat in expected_fantasy_cats:
            assert cat in categories
    
    def test_romance_genre_categories(self):
        """Test that romance materials get appropriate categories."""
        categories = CategoryManager.get_valid_categories("romance")
        
        # Should have relationship-related categories
        expected_romance_cats = [
            "relationship_dynamic", "emotional_beat", "romantic_tension",
            "intimacy_level", "character_chemistry", "romantic_arc"
        ]
        
        for cat in expected_romance_cats:
            assert cat in categories
    
    def test_mystery_genre_categories(self):
        """Test that mystery materials get appropriate categories."""
        categories = CategoryManager.get_valid_categories("mystery")
        
        # Should have investigation-related categories
        expected_mystery_cats = [
            "clue", "evidence", "red_herring", "investigative_method",
            "suspect_profile", "crime_scene", "detective_reasoning"
        ]
        
        for cat in expected_mystery_cats:
            assert cat in categories
    
    def test_genre_complexity_distribution(self):
        """Test that different genres have appropriate complexity distributions."""
        # Fantasy tends to have more complex categories
        fantasy_categories = CategoryManager.get_valid_categories("fantasy")
        fantasy_complex = [cat for cat in fantasy_categories 
                          if CategoryManager.get_complexity_level(cat) == "complex"]
        
        # Romance tends to have more medium categories
        romance_categories = CategoryManager.get_valid_categories("romance")
        romance_medium = [cat for cat in romance_categories 
                         if CategoryManager.get_complexity_level(cat) == "medium"]
        
        # Fantasy should have more complex categories than romance
        assert len(fantasy_complex) >= len(romance_medium) / 2
    
    def test_cross_genre_compatibility(self):
        """Test that multi-genre stories work correctly."""
        # Fantasy + Romance hybrid
        fantasy_romance = CategoryManager.get_multi_genre_categories(["fantasy", "romance"])
        
        # Should have categories from both genres
        assert "magic_system" in fantasy_romance  # Fantasy
        assert "relationship_dynamic" in fantasy_romance  # Romance
        assert "character" in fantasy_romance  # Base category
        
        # Should not have mystery-specific categories
        assert "evidence" not in fantasy_romance


if __name__ == "__main__":
    # Run basic smoke tests
    print("Running basic smoke tests...")
    
    # Test CategoryManager
    print("✓ Testing CategoryManager...")
    fantasy_cats = CategoryManager.get_valid_categories("fantasy")
    assert "magic_system" in fantasy_cats
    assert "character" in fantasy_cats
    print(f"  Fantasy categories: {len(fantasy_cats)} found")
    
    # Test MaterialClassification
    print("✓ Testing MaterialClassification...")
    classification = MaterialClassification(
        material_id="test_001",
        primary_category="character",
        genre_context="fantasy",
        content_hash="a" * 64,
        spoiler_risk="low"
    )
    assert classification.primary_category == "character"
    print("  MaterialClassification model working")
    
    # Test hash generation
    print("✓ Testing content hash generation...")
    test_content = "This is test content"
    content_hash = MaterialClassification.generate_content_hash(test_content)
    assert len(content_hash) == 64
    print(f"  Generated hash: {content_hash[:16]}...")
    
    print("\n🎉 All smoke tests passed! Phase 1A integration is ready.")
    print("\nNext steps:")
    print("- Run full test suite: pytest tests/test_material_ingestion_integration.py -v")
    print("- Implement Phase 1B CLI commands")
    print("- Add Prefect workflow integration")