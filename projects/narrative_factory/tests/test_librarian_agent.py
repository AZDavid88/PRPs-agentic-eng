"""
Comprehensive test suite for LibrarianAgent implementation.

Tests LibrarianAgent core functionality, integration with memory/embedding services,
security validation, performance characteristics, and Prefect workflow integration.
"""

import asyncio
import pytest
import time
from typing import List, Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.librarian import LibrarianAgent, analyze_materials_direct
from src.models.librarian_models import (
    MaterialAnalysisRequest,
    MaterialAnalysisResponse,
    MaterialAnalysisResult,
    CrossReference,
    QualityAssessment,
    ProcessingMetrics,
    LibrarianError,
    EmbeddingGenerationError,
    MemoryStorageError,
    MaterialProcessingError,
    CrossReferenceGenerationError
)
from src.models.material_models import MaterialClassification
from src.memory.service import MemoryService


# Global fixtures available to all test classes
@pytest.fixture
def sample_materials() -> List[MaterialClassification]:
    """Create sample materials for testing."""
    return [
        MaterialClassification(
            material_id="char_001",
            primary_category="character",
            secondary_categories=[],
            category_confidence={"character": 0.95},
            genre_context="fantasy",
            additional_genres=[],
            available_categories=["character", "setting", "plot_element"],
            classification_method="genre_extended",
            complexity_level="medium",
            content_hash="a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3",
            extracted_entities=["Elena"],
            content_length=156,
            metadata={"source": "character_sheet"}
        ),
        MaterialClassification(
            material_id="setting_001",
            primary_category="setting",
            secondary_categories=[],
            category_confidence={"setting": 0.88},
            genre_context="fantasy",
            additional_genres=[],
            available_categories=["character", "setting", "plot_element"],
            classification_method="genre_extended",
            complexity_level="medium",
            content_hash="b665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae4",
            extracted_entities=["Valdris"],
            content_length=142,
            metadata={"source": "world_guide"}
        ),
        MaterialClassification(
            material_id="plot_001",
            primary_category="plot_element",
            secondary_categories=[],
            category_confidence={"plot_element": 0.92},
            genre_context="fantasy",
            additional_genres=[],
            available_categories=["character", "setting", "plot_element"],
            classification_method="genre_extended",
            complexity_level="medium",
            content_hash="c665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae5",
            extracted_entities=["queen"],
            content_length=129,
            metadata={"source": "story_outline"}
        )
    ]


@pytest.fixture
def mock_memory_service():
    """Create mock memory service for testing."""
    mock_service = AsyncMock(spec=MemoryService)
    mock_service.store_material_embeddings.return_value = {
        "status": "success",
        "collection": "materials_test",
        "embeddings_stored": 3,
        "material_id": "test_material",
        "storage_result": {"points_stored": 3}
    }
    mock_service.retrieve_related_materials.return_value = []
    mock_service.fetch_material_analysis_context.return_value = {
        "material_count": 1,
        "analysis_depth": "standard"
    }
    return mock_service


@pytest.fixture
def mock_embedding_service():
    """Create mock embedding service for testing."""
    mock_service = AsyncMock()
    mock_service.generate_embeddings_batch.return_value = [
        [0.1] * 1536,  # Mock OpenAI text-embedding-3-small dimension
        [0.2] * 1536,
        [0.3] * 1536
    ]
    return mock_service


class TestLibrarianAgentCore:
    """Test LibrarianAgent core functionality and initialization."""
    
    def test_librarian_agent_initialization(self, mock_memory_service):
        """Test LibrarianAgent initialization with proper dependencies."""
        agent = LibrarianAgent(client_type="openai", memory_service=mock_memory_service)
        
        assert agent.persona_name == "librarian"
        assert agent.client_type == "openai"
        assert agent.memory_service == mock_memory_service
        assert agent.max_concurrent_materials == 20
        assert agent.default_embedding_model == "text-embedding-3-small"
        assert agent.similarity_threshold == 0.7
        assert isinstance(agent.processing_metrics, ProcessingMetrics)
    
    def test_librarian_agent_initialization_defaults(self):
        """Test LibrarianAgent initialization with default parameters."""
        agent = LibrarianAgent()
        
        assert agent.persona_name == "librarian"
        assert agent.client_type == "openai"
        assert agent.memory_service is not None
        assert hasattr(agent, 'embedding_service')
    
    @pytest.mark.asyncio
    async def test_librarian_agent_close(self, mock_memory_service, mock_embedding_service):
        """Test LibrarianAgent cleanup functionality."""
        agent = LibrarianAgent(memory_service=mock_memory_service)
        agent.embedding_service = mock_embedding_service
        
        await agent.close()
        
        mock_embedding_service.close.assert_called_once()
        mock_memory_service.close.assert_called_once()


class TestMaterialAnalysisRequest:
    """Test MaterialAnalysisRequest validation and configuration."""
    
    def test_material_analysis_request_creation(self, sample_materials):
        """Test creating MaterialAnalysisRequest with valid parameters."""
        request = MaterialAnalysisRequest(
            classifications=sample_materials,
            analysis_depth="comprehensive",
            enable_cross_references=True,
            enable_quality_assessment=True,
            concurrent_limit=15
        )
        
        assert len(request.classifications) == 3
        assert request.analysis_depth == "comprehensive"
        assert request.enable_cross_references is True
        assert request.enable_quality_assessment is True
        assert request.concurrent_limit == 15
    
    def test_material_analysis_request_defaults(self, sample_materials):
        """Test MaterialAnalysisRequest with default parameters."""
        request = MaterialAnalysisRequest(classifications=sample_materials)
        
        assert request.analysis_depth == "standard"
        assert request.enable_cross_references is True
        assert request.enable_quality_assessment is True
        assert request.concurrent_limit == 10
        assert request.story_context is None
    
    def test_material_analysis_request_validation(self, sample_materials):
        """Test MaterialAnalysisRequest parameter validation."""
        # Test concurrent limit boundaries
        with pytest.raises(ValueError):
            MaterialAnalysisRequest(classifications=sample_materials, concurrent_limit=0)
        
        with pytest.raises(ValueError):
            MaterialAnalysisRequest(classifications=sample_materials, concurrent_limit=21)
        
        # Valid boundary values should work
        request_min = MaterialAnalysisRequest(classifications=sample_materials, concurrent_limit=1)
        assert request_min.concurrent_limit == 1
        
        request_max = MaterialAnalysisRequest(classifications=sample_materials, concurrent_limit=20)
        assert request_max.concurrent_limit == 20


class TestMaterialAnalysisCore:
    """Test core material analysis functionality."""
    
    @pytest.fixture
    def librarian_agent(self, mock_memory_service, mock_embedding_service):
        """Create LibrarianAgent with mocked dependencies."""
        agent = LibrarianAgent(memory_service=mock_memory_service)
        agent.embedding_service = mock_embedding_service
        return agent
    
    @pytest.mark.asyncio
    async def test_analyze_materials_basic(self, librarian_agent, sample_materials):
        """Test basic material analysis functionality."""
        request = MaterialAnalysisRequest(
            classifications=sample_materials,
            analysis_depth="standard",
            enable_cross_references=False,  # Disable for simpler test
            enable_quality_assessment=True
        )
        
        # Mock the retry method that's actually called by the batch processor
        async def mock_analyze_single_material_with_retry(classification, request, metrics, max_retries=3):
            from src.models.librarian_models import MaterialAnalysisResult
            result = MaterialAnalysisResult(
                source_classification=classification,
                vector_storage_metadata={
                    "chunks_count": 3,
                    "embeddings_generated": 3,
                    "storage_result": {"status": "success"},
                    "processing_strategy": classification.primary_category,
                    "primary_embedding": [0.1] * 1536
                },
                cross_references=[],
                quality_assessment=QualityAssessment(
                    is_acceptable=True,
                    quality_score=0.85,
                    issues_found=[],
                    recommendations=[]
                ) if request.enable_quality_assessment else None,
                specialized_analysis={
                    "analysis_type": classification.primary_category,
                    "content_length": classification.content_length,
                    "word_count": max(1, classification.content_length // 6)
                }
            )
            result.processing_time = 0.1  # Add processing time
            metrics.record_processing_step("material")
            return result
        
        with patch.object(librarian_agent, '_analyze_single_material_with_retry', side_effect=mock_analyze_single_material_with_retry):
            
            response = await librarian_agent.analyze_materials(request)
            
            assert isinstance(response, MaterialAnalysisResponse)
            assert response.successful_count == 3
            assert response.failed_count == 0
            assert len(response.results) == 3
            assert response.cross_references_generated == 0  # Disabled
            assert response.processing_time > 0
    
    @pytest.mark.asyncio
    async def test_analyze_materials_with_cross_references(self, librarian_agent, sample_materials):
        """Test material analysis with cross-reference generation."""
        request = MaterialAnalysisRequest(
            classifications=sample_materials,
            enable_cross_references=True,
            enable_quality_assessment=False
        )
        
        # Mock the retry method and cross-reference generation
        async def mock_analyze_single_with_retry_crossref(classification, request, metrics, max_retries=3):
            from src.models.librarian_models import MaterialAnalysisResult
            result = MaterialAnalysisResult(
                source_classification=classification,
                vector_storage_metadata={
                    "chunks_count": 2,
                    "embeddings_generated": 2,
                    "storage_result": {"status": "success"},
                    "processing_strategy": classification.primary_category,
                    "primary_embedding": [0.1] * 1536
                },
                cross_references=[],
                specialized_analysis={"analysis_type": classification.primary_category}
            )
            result.processing_time = 0.1
            metrics.record_processing_step("material")
            return result
        
        with patch.object(librarian_agent, '_analyze_single_material_with_retry', side_effect=mock_analyze_single_with_retry_crossref), \
             patch.object(librarian_agent, '_generate_cross_references') as mock_cross_refs:
            
            mock_cross_refs.return_value = [
                CrossReference(
                    source_material_id="char_001",
                    target_material_id="setting_001",
                    relationship_type="references",
                    confidence=0.75,
                    context="Character references setting"
                )
            ]
            
            response = await librarian_agent.analyze_materials(request)
            
            assert response.cross_references_generated == 1
            assert len(response.results[0].cross_references) > 0
    
    @pytest.mark.asyncio
    async def test_analyze_materials_error_handling(self, librarian_agent, sample_materials):
        """Test material analysis error handling and partial success."""
        request = MaterialAnalysisRequest(classifications=sample_materials)
        
        # Mock one material failing, others succeeding
        async def mock_analyze_single_with_retry_error(classification, request, metrics, max_retries=3):
            if classification.material_id == "char_001":
                raise EmbeddingGenerationError("Mock embedding failure")
            
            from src.models.librarian_models import MaterialAnalysisResult
            result = MaterialAnalysisResult(
                source_classification=classification,
                vector_storage_metadata={
                    "chunks_count": 2,
                    "embeddings_generated": 2,
                    "storage_result": {"status": "success"},
                    "processing_strategy": classification.primary_category,
                    "primary_embedding": [0.1] * 1536
                },
                cross_references=[],
                specialized_analysis={"analysis_type": "test"}
            )
            result.processing_time = 0.1
            metrics.record_processing_step("material")
            return result
        
        with patch.object(librarian_agent, '_analyze_single_material_with_retry', side_effect=mock_analyze_single_with_retry_error):
            
            response = await librarian_agent.analyze_materials(request)
            
            # Should have partial success
            assert response.successful_count == 2
            assert response.failed_count == 1
            assert response.get_success_rate() == 66.7  # 2/3 * 100


class TestConcurrentProcessing:
    """Test concurrent processing and performance characteristics."""
    
    @pytest.fixture
    def librarian_agent(self, mock_memory_service, mock_embedding_service):
        """Create LibrarianAgent with mocked dependencies."""
        agent = LibrarianAgent(memory_service=mock_memory_service)
        agent.embedding_service = mock_embedding_service
        return agent
    
    def test_create_smart_batches(self, librarian_agent, sample_materials):
        """Test intelligent batch creation for concurrent processing."""
        # Test with small batch size
        batches = librarian_agent._create_smart_batches(sample_materials, max_concurrent=4)
        
        assert len(batches) > 0
        assert all(isinstance(batch, list) for batch in batches)
        assert sum(len(batch) for batch in batches) == len(sample_materials)
    
    def test_create_smart_batches_large_dataset(self, librarian_agent):
        """Test batch creation with larger dataset."""
        # Create larger dataset
        large_materials = [
            MaterialClassification(
                id=f"material_{i}",
                content=f"Content for material {i}",
                category="character" if i % 2 == 0 else "setting",
                confidence_score=0.8
            )
            for i in range(50)
        ]
        
        batches = librarian_agent._create_smart_batches(large_materials, max_concurrent=10)
        
        assert len(batches) > 1
        assert all(len(batch) <= 5 for batch in batches)  # max_concurrent // 2
        assert sum(len(batch) for batch in batches) == 50
    
    @pytest.mark.asyncio
    async def test_concurrent_processing_limits(self, librarian_agent, sample_materials):
        """Test that concurrent processing respects limits."""
        request = MaterialAnalysisRequest(
            classifications=sample_materials,
            concurrent_limit=2  # Low limit for testing
        )
        
        processing_times = []
        
        async def mock_analyze_single_material(classification, request):
            start_time = time.time()
            await asyncio.sleep(0.1)  # Simulate processing time
            processing_times.append(time.time() - start_time)
            return MaterialAnalysisResult(
                source_classification=classification,
                vector_storage_metadata={"test": True},
                specialized_analysis={"analysis_type": "test"}
            )
        
        with patch.object(librarian_agent, '_analyze_single_material', side_effect=mock_analyze_single_material):
            response = await librarian_agent.analyze_materials(request)
            
            assert response.successful_count == 3
            # Verify concurrent processing actually happened (total time < sequential time)
            assert response.processing_time < 0.3  # Should be < 3 * 0.1 if concurrent


class TestSecurityValidation:
    """Test security features and input validation."""
    
    @pytest.fixture
    def librarian_agent(self, mock_memory_service, mock_embedding_service):
        """Create LibrarianAgent with mocked dependencies."""
        agent = LibrarianAgent(memory_service=mock_memory_service)
        agent.embedding_service = mock_embedding_service
        return agent
    
    def test_input_validation_empty_materials(self, librarian_agent):
        """Test validation of empty materials list."""
        with pytest.raises(ValueError, match="Materials list cannot be empty"):
            MaterialAnalysisRequest(classifications=[])
    
    def test_input_validation_concurrent_limits(self, sample_materials):
        """Test validation of concurrent processing limits."""
        # Test lower bound
        with pytest.raises(ValueError):
            MaterialAnalysisRequest(classifications=sample_materials, concurrent_limit=0)
        
        # Test upper bound
        with pytest.raises(ValueError):
            MaterialAnalysisRequest(classifications=sample_materials, concurrent_limit=21)
        
        # Test valid bounds
        request_min = MaterialAnalysisRequest(classifications=sample_materials, concurrent_limit=1)
        assert request_min.concurrent_limit == 1
        
        request_max = MaterialAnalysisRequest(classifications=sample_materials, concurrent_limit=20)
        assert request_max.concurrent_limit == 20
    
    def test_material_size_validation(self, librarian_agent):
        """Test validation of material content size."""
        # Create oversized material
        oversized_content = "x" * 60000  # Larger than typical limits
        oversized_material = MaterialClassification(
            id="oversized",
            content=oversized_content,
            category="character",
            confidence_score=0.8
        )
        
        # The agent should handle this gracefully (log warning but continue)
        request = MaterialAnalysisRequest(classifications=[oversized_material])
        
        # Should not raise exception - just log warning
        assert len(request.classifications) == 1
        assert len(request.classifications[0].content) == 60000
    
    @pytest.mark.asyncio
    async def test_error_isolation(self, librarian_agent):
        """Test that individual material failures don't crash entire batch."""
        materials = [
            MaterialClassification(id="good1", content="Good content 1", category="character", confidence_score=0.9),
            MaterialClassification(id="bad", content="Bad content", category="character", confidence_score=0.9),
            MaterialClassification(id="good2", content="Good content 2", category="setting", confidence_score=0.9)
        ]
        
        def mock_process_side_effect(content, category, material_id):
            if material_id == "bad":
                raise MemoryStorageError("Mock storage failure")
            return {"chunks_count": 1, "embeddings_generated": 1, "storage_result": {"status": "success"}}
        
        with patch.object(librarian_agent, '_process_material_with_late_chunking', side_effect=mock_process_side_effect), \
             patch.object(librarian_agent, '_perform_specialized_analysis', return_value={"test": True}):
            
            request = MaterialAnalysisRequest(classifications=materials)
            response = await librarian_agent.analyze_materials(request)
            
            assert response.successful_count == 2
            assert response.failed_count == 1
            assert len(response.results) == 2  # Only successful results included


class TestSpecializedAnalysis:
    """Test specialized analysis functionality for different material types."""
    
    @pytest.fixture
    def librarian_agent(self, mock_memory_service, mock_embedding_service):
        """Create LibrarianAgent with mocked dependencies."""
        agent = LibrarianAgent(memory_service=mock_memory_service)
        agent.embedding_service = mock_embedding_service
        return agent
    
    @pytest.mark.asyncio
    async def test_character_analysis(self, librarian_agent):
        """Test specialized analysis for character materials."""
        character_material = MaterialClassification(
            id="char_test",
            content="Elena is confident and bold, with piercing eyes and a strong personality. She says 'I'll protect everyone.'",
            category="character",
            confidence_score=0.95
        )
        
        analysis = await librarian_agent._analyze_character_material(character_material)
        
        assert analysis["mentions_appearance"] is True  # "eyes"
        assert analysis["mentions_personality"] is True  # "personality"
        assert analysis["has_dialogue"] is True  # quotes
    
    @pytest.mark.asyncio
    async def test_setting_analysis(self, librarian_agent):
        """Test specialized analysis for setting materials."""
        setting_material = MaterialClassification(
            id="setting_test",
            content="The ancient castle stands on a mountain, with the sound of wind and the smell of old stone.",
            category="setting",
            confidence_score=0.90
        )
        
        analysis = await librarian_agent._analyze_setting_material(setting_material)
        
        assert analysis["location_type"] == "medieval"  # "castle"
        assert analysis["has_sensory_details"] is True  # "sound", "smell"
    
    @pytest.mark.asyncio
    async def test_prose_style_guide_analysis(self, librarian_agent):
        """Test specialized analysis for prose style guide materials."""
        style_material = MaterialClassification(
            id="style_test",
            content="Style: Formal and elegant prose with rich, descriptive language. Use vivid imagery and detailed descriptions.",
            category="prose_style_guide",
            confidence_score=0.92
        )
        
        analysis = await librarian_agent._analyze_prose_style_guide(style_material)
        
        assert analysis["style_indicators"]["formal"] > 0
        assert analysis["style_indicators"]["descriptive"] > 0
        assert analysis["dominant_style"] in ["formal", "descriptive"]


class TestCrossReferenceGeneration:
    """Test cross-reference generation functionality."""
    
    @pytest.fixture
    def librarian_agent(self, mock_memory_service, mock_embedding_service):
        """Create LibrarianAgent with mocked dependencies."""
        agent = LibrarianAgent(memory_service=mock_memory_service)
        agent.embedding_service = mock_embedding_service
        return agent
    
    def test_cosine_similarity_calculation(self, librarian_agent):
        """Test cosine similarity calculation."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        vec3 = [1.0, 0.0, 0.0]
        
        # Orthogonal vectors should have similarity 0
        similarity_orthogonal = librarian_agent._cosine_similarity(vec1, vec2)
        assert abs(similarity_orthogonal - 0.0) < 1e-10
        
        # Identical vectors should have similarity 1
        similarity_identical = librarian_agent._cosine_similarity(vec1, vec3)
        assert abs(similarity_identical - 1.0) < 1e-10
    
    def test_relationship_type_determination(self, librarian_agent):
        """Test relationship type determination logic."""
        char_material = MaterialClassification(id="char1", content="test", category="character", confidence_score=0.9)
        setting_material = MaterialClassification(id="set1", content="test", category="setting", confidence_score=0.9)
        char_material2 = MaterialClassification(id="char2", content="test", category="character", confidence_score=0.9)
        
        # Same category, high similarity
        rel_type1 = librarian_agent._determine_relationship_type(char_material, char_material2, 0.95)
        assert rel_type1 == "similar"
        
        # Same category, medium similarity
        rel_type2 = librarian_agent._determine_relationship_type(char_material, char_material2, 0.8)
        assert rel_type2 == "references"
        
        # Different category, high similarity
        rel_type3 = librarian_agent._determine_relationship_type(char_material, setting_material, 0.9)
        assert rel_type3 == "expands"
        
        # Different category, medium similarity
        rel_type4 = librarian_agent._determine_relationship_type(char_material, setting_material, 0.75)
        assert rel_type4 == "references"
    
    @pytest.mark.asyncio
    async def test_cross_reference_generation_insufficient_materials(self, librarian_agent):
        """Test cross-reference generation with insufficient materials."""
        # Single material - should return empty list
        single_result = [
            MaterialAnalysisResult(
                source_classification=MaterialClassification(id="test", content="test", category="test", confidence_score=0.8),
                vector_storage_metadata={"primary_embedding": [0.1] * 1536}
            )
        ]
        
        cross_refs = await librarian_agent._generate_cross_references(single_result)
        assert len(cross_refs) == 0
    
    @pytest.mark.asyncio
    async def test_cross_reference_generation_success(self, librarian_agent):
        """Test successful cross-reference generation."""
        # Two materials with similar embeddings
        results = [
            MaterialAnalysisResult(
                source_classification=MaterialClassification(id="char1", content="test1", category="character", confidence_score=0.9),
                vector_storage_metadata={"primary_embedding": [0.8] * 1536}
            ),
            MaterialAnalysisResult(
                source_classification=MaterialClassification(id="char2", content="test2", category="character", confidence_score=0.9),
                vector_storage_metadata={"primary_embedding": [0.85] * 1536}  # Very similar
            )
        ]
        
        cross_refs = await librarian_agent._generate_cross_references(results)
        
        # Should generate cross-references due to high similarity
        assert len(cross_refs) > 0
        assert cross_refs[0].source_material_id == "char1"
        assert cross_refs[0].target_material_id == "char2"
        assert cross_refs[0].confidence > 0.7  # Above threshold


class TestQualityAssessment:
    """Test quality assessment functionality."""
    
    @pytest.fixture
    def librarian_agent(self, mock_memory_service, mock_embedding_service):
        """Create LibrarianAgent with mocked dependencies."""
        agent = LibrarianAgent(memory_service=mock_memory_service)
        agent.embedding_service = mock_embedding_service
        return agent
    
    @pytest.mark.asyncio
    async def test_quality_assessment_good_material(self, librarian_agent):
        """Test quality assessment for high-quality material."""
        good_material = MaterialClassification(
            id="good_test",
            content="This is a well-written character description with sufficient detail and clear personality traits that provide meaningful context for the story.",
            category="character",
            confidence_score=0.95
        )
        
        assessment = await librarian_agent._assess_material_quality(good_material, "standard")
        
        assert assessment.is_acceptable is True
        assert assessment.quality_score > 0.6
        assert len(assessment.issues_found) == 0
    
    @pytest.mark.asyncio
    async def test_quality_assessment_poor_material(self, librarian_agent):
        """Test quality assessment for low-quality material."""
        poor_material = MaterialClassification(
            id="poor_test",
            content="Short.",  # Too short
            category="character",
            confidence_score=0.4  # Low confidence
        )
        
        assessment = await librarian_agent._assess_material_quality(poor_material, "standard")
        
        assert assessment.is_acceptable is False
        assert assessment.quality_score < 0.6
        assert len(assessment.issues_found) > 0
        assert any("too short" in issue.lower() for issue in assessment.issues_found)
        assert any("confidence" in issue.lower() for issue in assessment.issues_found)
    
    @pytest.mark.asyncio
    async def test_quality_assessment_medium_material(self, librarian_agent):
        """Test quality assessment for medium-quality material."""
        medium_material = MaterialClassification(
            id="medium_test",
            content="Elena is a character with some traits but lacks detailed description and development.",
            category="character",
            confidence_score=0.75
        )
        
        assessment = await librarian_agent._assess_material_quality(medium_material, "standard")
        
        # Should have some issues but might still be acceptable
        assert isinstance(assessment.is_acceptable, bool)
        assert 0.0 <= assessment.quality_score <= 1.0
        # May or may not have issues depending on specific criteria


class TestDirectAnalysisFunction:
    """Test the direct analysis function for convenience usage."""
    
    @pytest.mark.asyncio
    async def test_analyze_materials_direct_function(self, sample_materials):
        """Test the direct analysis function."""
        with patch('src.agents.librarian.LibrarianAgent') as MockAgent:
            mock_agent_instance = AsyncMock()
            MockAgent.return_value = mock_agent_instance
            
            mock_response = MaterialAnalysisResponse(
                request_id="test_123",
                results=[],
                successful_count=3,
                failed_count=0,
                processing_time=1.5,
                cross_references_generated=2,
                quality_issues_found=0,
                metrics=ProcessingMetrics()
            )
            mock_agent_instance.analyze_materials.return_value = mock_response
            
            response = await analyze_materials_direct(
                materials=sample_materials,
                analysis_depth="comprehensive"
            )
            
            assert response.successful_count == 3
            assert response.failed_count == 0
            mock_agent_instance.close.assert_called_once()


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])