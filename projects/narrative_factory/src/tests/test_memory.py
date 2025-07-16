"""
Unit tests for memory pipeline components.
Tests QdrantService, EmbeddingService, and two-tiered retrieval.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

# Add the src directory to the path so we can import from memory
src_path = Path(__file__).parent.parent
sys.path.insert(0, str(src_path))

# Try different import approaches
try:
    from agents.models import ContextRetrievalResult
    from memory.embedding_service import (
        EmbeddingService,
        JinaEmbeddingProvider,
        LocalSentenceTransformersProvider,
    )
    from memory.qdrant import QdrantService
except ImportError:
    # Alternative import approach for testing
    import importlib.util

    # Import QdrantService
    spec = importlib.util.spec_from_file_location("qdrant", src_path / "memory" / "qdrant.py")
    qdrant_module = importlib.util.module_from_spec(spec)
    sys.modules["qdrant"] = qdrant_module
    spec.loader.exec_module(qdrant_module)
    QdrantService = qdrant_module.QdrantService

    # Import EmbeddingService
    spec = importlib.util.spec_from_file_location("embedding_service", src_path / "memory" / "embedding_service.py")
    embedding_module = importlib.util.module_from_spec(spec)
    sys.modules["embedding_service"] = embedding_module
    spec.loader.exec_module(embedding_module)
    EmbeddingService = embedding_module.EmbeddingService
    LocalSentenceTransformersProvider = embedding_module.LocalSentenceTransformersProvider
    JinaEmbeddingProvider = embedding_module.JinaEmbeddingProvider

    # Import ContextRetrievalResult
    spec = importlib.util.spec_from_file_location("models", src_path / "agents" / "models.py")
    models_module = importlib.util.module_from_spec(spec)
    sys.modules["models"] = models_module
    spec.loader.exec_module(models_module)
    ContextRetrievalResult = models_module.ContextRetrievalResult


class TestEmbeddingService:
    """Test the EmbeddingService and its providers."""

    def test_local_provider_initialization(self):
        """Test that LocalSentenceTransformersProvider initializes correctly."""
        with patch('memory.embedding_service.SENTENCE_TRANSFORMERS_AVAILABLE', True):
            provider = LocalSentenceTransformersProvider()
            assert provider.model_name == "all-MiniLM-L6-v2"
            assert provider.get_embedding_dimension() == 384

    def test_local_provider_initialization_without_sentence_transformers(self):
        """Test that LocalSentenceTransformersProvider fails without sentence-transformers."""
        with patch('memory.embedding_service.SENTENCE_TRANSFORMERS_AVAILABLE', False):
            with pytest.raises(ImportError, match="sentence-transformers is required"):
                LocalSentenceTransformersProvider()

    @pytest.mark.asyncio
    async def test_local_provider_generate_embeddings(self):
        """Test embedding generation with mocked sentence-transformers."""
        with patch('memory.embedding_service.SENTENCE_TRANSFORMERS_AVAILABLE', True):
            with patch('memory.embedding_service.SentenceTransformer') as mock_st:
                # Setup mock
                mock_model = Mock()
                mock_model.encode.return_value = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
                mock_st.return_value = mock_model

                provider = LocalSentenceTransformersProvider()
                embeddings = await provider.generate_embeddings(["text1", "text2"])

                assert len(embeddings) == 2
                assert embeddings[0] == [0.1, 0.2, 0.3]
                assert embeddings[1] == [0.4, 0.5, 0.6]
                mock_model.encode.assert_called_once_with(["text1", "text2"])

    def test_jina_provider_initialization(self):
        """Test JinaEmbeddingProvider initialization."""
        with patch('memory.embedding_service.HTTPX_AVAILABLE', True):
            with patch('memory.embedding_service.TENACITY_AVAILABLE', True):
                with patch.dict('os.environ', {'JINA_API_KEY': 'test_key'}):
                    provider = JinaEmbeddingProvider()
                    assert provider.api_key == 'test_key'
                    assert provider.model == 'jina-embeddings-v4'
                    assert provider.get_embedding_dimension() == 1024

    def test_jina_provider_initialization_without_api_key(self):
        """Test JinaEmbeddingProvider fails without API key."""
        with patch('memory.embedding_service.HTTPX_AVAILABLE', True):
            with patch('memory.embedding_service.TENACITY_AVAILABLE', True):
                with patch.dict('os.environ', {}, clear=True):
                    with pytest.raises(ValueError, match="JINA_API_KEY environment variable"):
                        JinaEmbeddingProvider()

    @pytest.mark.asyncio
    async def test_jina_provider_generate_embeddings(self):
        """Test Jina AI embedding generation with mocked HTTP client."""
        with patch('memory.embedding_service.HTTPX_AVAILABLE', True):
            with patch('memory.embedding_service.TENACITY_AVAILABLE', True):
                with patch.dict('os.environ', {'JINA_API_KEY': 'test_key'}):
                    # Mock response
                    mock_response = Mock()
                    mock_response.json.return_value = {
                        "data": [
                            {"embedding": [0.1, 0.2, 0.3]},
                            {"embedding": [0.4, 0.5, 0.6]}
                        ],
                        "model": "jina-embeddings-v4",
                        "usage": {"total_tokens": 10}
                    }
                    mock_response.raise_for_status.return_value = None

                    # Mock client
                    mock_client = AsyncMock()
                    mock_client.post.return_value = mock_response

                    with patch('memory.embedding_service.httpx.AsyncClient', return_value=mock_client):
                        provider = JinaEmbeddingProvider()
                        embeddings = await provider.generate_embeddings(["text1", "text2"])

                        assert len(embeddings) == 2
                        assert embeddings[0] == [0.1, 0.2, 0.3]
                        assert embeddings[1] == [0.4, 0.5, 0.6]

    def test_embedding_service_initialization(self):
        """Test EmbeddingService initialization with different providers."""
        with patch('memory.embedding_service.SENTENCE_TRANSFORMERS_AVAILABLE', True):
            # Test local provider
            service = EmbeddingService(provider="local")
            assert service.provider_name == "local"
            assert isinstance(service.provider, LocalSentenceTransformersProvider)

    @pytest.mark.asyncio
    async def test_embedding_service_generate_single_embedding(self):
        """Test single embedding generation."""
        with patch('memory.embedding_service.SENTENCE_TRANSFORMERS_AVAILABLE', True):
            with patch('memory.embedding_service.SentenceTransformer') as mock_st:
                mock_model = Mock()
                mock_model.encode.return_value = [[0.1, 0.2, 0.3]]
                mock_st.return_value = mock_model

                service = EmbeddingService(provider="local")
                embedding = await service.generate_embedding("test text")

                assert embedding == [0.1, 0.2, 0.3]


class TestQdrantService:
    """Test the QdrantService class."""

    def test_qdrant_service_initialization(self):
        """Test QdrantService initialization."""
        with patch('memory.qdrant.QDRANT_AVAILABLE', True):
            with patch('memory.qdrant.SENTENCE_TRANSFORMERS_AVAILABLE', True):
                with patch('memory.qdrant.AsyncQdrantClient') as mock_client:
                    service = QdrantService()
                    assert service.url == "http://localhost:6333"
                    assert service.embedding_dimension == 384
                    mock_client.assert_called_once()

    def test_qdrant_service_initialization_without_qdrant(self):
        """Test QdrantService fails without qdrant-client."""
        with patch('memory.qdrant.QDRANT_AVAILABLE', False):
            with pytest.raises(ImportError, match="qdrant-client is required"):
                QdrantService()

    @pytest.mark.asyncio
    async def test_create_collections(self):
        """Test collection creation."""
        with patch('memory.qdrant.QDRANT_AVAILABLE', True):
            with patch('memory.qdrant.SENTENCE_TRANSFORMERS_AVAILABLE', True):
                mock_client = AsyncMock()
                mock_client.collection_exists = AsyncMock(return_value=False)
                mock_client.create_collection = AsyncMock()

                with patch('memory.qdrant.AsyncQdrantClient', return_value=mock_client):
                    service = QdrantService()
                    await service.create_collections()

                    # Should create both collections
                    assert mock_client.create_collection.call_count == 2

                    # Check the calls
                    calls = mock_client.create_collection.call_args_list
                    collection_names = [call[1]['collection_name'] for call in calls]
                    assert "world_bible" in collection_names
                    assert "story_so_far" in collection_names

    @pytest.mark.asyncio
    async def test_embed_text(self):
        """Test text embedding generation."""
        with patch('memory.qdrant.QDRANT_AVAILABLE', True):
            with patch('memory.qdrant.SENTENCE_TRANSFORMERS_AVAILABLE', True):
                with patch('memory.qdrant.SentenceTransformer') as mock_st:
                    mock_model = Mock()
                    mock_model.encode.return_value = Mock()
                    mock_model.encode.return_value.tolist.return_value = [0.1, 0.2, 0.3]
                    mock_st.return_value = mock_model

                    mock_client = AsyncMock()
                    with patch('memory.qdrant.AsyncQdrantClient', return_value=mock_client):
                        service = QdrantService()
                        embedding = await service._embed_text("test text")

                        assert embedding == [0.1, 0.2, 0.3]
                        mock_model.encode.assert_called_once_with("test text")

    @pytest.mark.asyncio
    async def test_ingest_document(self):
        """Test single document ingestion."""
        with patch('memory.qdrant.QDRANT_AVAILABLE', True):
            with patch('memory.qdrant.SENTENCE_TRANSFORMERS_AVAILABLE', True):
                with patch('memory.qdrant.SentenceTransformer') as mock_st:
                    mock_model = Mock()
                    mock_model.encode.return_value = Mock()
                    mock_model.encode.return_value.tolist.return_value = [0.1, 0.2, 0.3]
                    mock_st.return_value = mock_model

                    mock_client = AsyncMock()
                    mock_client.upsert = AsyncMock()

                    with patch('memory.qdrant.AsyncQdrantClient', return_value=mock_client):
                        service = QdrantService()

                        await service.ingest_document(
                            doc_id="test_doc",
                            content="test content",
                            collection_name="test_collection",
                            metadata={"type": "test"}
                        )

                        mock_client.upsert.assert_called_once()
                        call_args = mock_client.upsert.call_args
                        assert call_args[1]['collection_name'] == "test_collection"
                        assert len(call_args[1]['points']) == 1

                        point = call_args[1]['points'][0]
                        assert point.id == "test_doc"
                        assert point.vector == [0.1, 0.2, 0.3]
                        assert point.payload['content'] == "test content"
                        assert point.payload['type'] == "test"

    @pytest.mark.asyncio
    async def test_fetch_context_for_director(self):
        """Test two-tiered context retrieval."""
        with patch('memory.qdrant.QDRANT_AVAILABLE', True):
            with patch('memory.qdrant.SENTENCE_TRANSFORMERS_AVAILABLE', True):
                with patch('memory.qdrant.SentenceTransformer') as mock_st:
                    mock_model = Mock()
                    mock_model.encode.return_value = Mock()
                    mock_model.encode.return_value.tolist.return_value = [0.1, 0.2, 0.3]
                    mock_st.return_value = mock_model

                    # Mock search results
                    spotlight_hit = Mock()
                    spotlight_hit.payload = {"content": "character info", "character": "selene"}
                    spotlight_hit.score = 0.9
                    spotlight_hit.id = "char_001"

                    ambient_hit = Mock()
                    ambient_hit.payload = {"content": "tension report", "status": "unresolved"}
                    ambient_hit.score = 0.8
                    ambient_hit.id = "tension_001"

                    mock_client = AsyncMock()
                    mock_client.search = AsyncMock()

                    # Configure search to return different results based on collection
                    def search_side_effect(*args, **kwargs):
                        collection_name = kwargs.get('collection_name')
                        if collection_name == "world_bible":
                            return [spotlight_hit]
                        elif collection_name == "story_so_far":
                            return [ambient_hit]
                        return []

                    mock_client.search.side_effect = search_side_effect

                    with patch('memory.qdrant.AsyncQdrantClient', return_value=mock_client):
                        service = QdrantService()

                        context = await service.fetch_context_for_director(
                            chapter_seed="Test chapter",
                            active_characters=["selene", "marcus"]
                        )

                        # Should have called search twice (spotlight + ambient)
                        assert mock_client.search.call_count == 2

                        # Check the results
                        assert isinstance(context, ContextRetrievalResult)
                        assert len(context.spotlight_context) == 1
                        assert len(context.ambient_echo) == 1

                        assert context.spotlight_context[0]['content'] == "character info"
                        assert context.spotlight_context[0]['score'] == 0.9

                        assert context.ambient_echo[0]['content'] == "tension report"
                        assert context.ambient_echo[0]['score'] == 0.8

    @pytest.mark.asyncio
    async def test_search_by_content(self):
        """Test generic content search."""
        with patch('memory.qdrant.QDRANT_AVAILABLE', True):
            with patch('memory.qdrant.SENTENCE_TRANSFORMERS_AVAILABLE', True):
                with patch('memory.qdrant.SentenceTransformer') as mock_st:
                    mock_model = Mock()
                    mock_model.encode.return_value = Mock()
                    mock_model.encode.return_value.tolist.return_value = [0.1, 0.2, 0.3]
                    mock_st.return_value = mock_model

                    # Mock search result
                    search_hit = Mock()
                    search_hit.payload = {"content": "search result"}
                    search_hit.score = 0.9
                    search_hit.id = "result_001"

                    mock_client = AsyncMock()
                    mock_client.search = AsyncMock(return_value=[search_hit])

                    with patch('memory.qdrant.AsyncQdrantClient', return_value=mock_client):
                        service = QdrantService()

                        results = await service.search_by_content(
                            query_text="test query",
                            collection_name="test_collection",
                            limit=5
                        )

                        assert len(results) == 1
                        assert results[0]['content'] == "search result"
                        assert results[0]['score'] == 0.9
                        assert results[0]['id'] == "result_001"

                        # Check search was called correctly
                        mock_client.search.assert_called_once()
                        call_args = mock_client.search.call_args
                        assert call_args[1]['collection_name'] == "test_collection"
                        assert call_args[1]['query_vector'] == [0.1, 0.2, 0.3]
                        assert call_args[1]['limit'] == 5


class TestIntegration:
    """Integration tests for memory pipeline components."""

    @pytest.mark.asyncio
    async def test_memory_pipeline_integration(self):
        """Test integration between embedding service and Qdrant service."""
        with patch('memory.qdrant.QDRANT_AVAILABLE', True):
            with patch('memory.qdrant.SENTENCE_TRANSFORMERS_AVAILABLE', True):
                with patch('memory.embedding_service.SENTENCE_TRANSFORMERS_AVAILABLE', True):
                    with patch('memory.qdrant.SentenceTransformer') as mock_st_qdrant:
                        with patch('memory.embedding_service.SentenceTransformer') as mock_st_embedding:
                            # Setup mocks
                            mock_model = Mock()
                            mock_model.encode.return_value = Mock()
                            mock_model.encode.return_value.tolist.return_value = [0.1, 0.2, 0.3]
                            mock_st_qdrant.return_value = mock_model
                            mock_st_embedding.return_value = mock_model

                            mock_client = AsyncMock()
                            mock_client.upsert = AsyncMock()
                            mock_client.collection_exists = AsyncMock(return_value=True)

                            with patch('memory.qdrant.AsyncQdrantClient', return_value=mock_client):
                                # Test services work together
                                qdrant_service = QdrantService()
                                embedding_service = EmbeddingService(provider="local")

                                # Generate embedding
                                embedding = await embedding_service.generate_embedding("test content")
                                assert embedding == [0.1, 0.2, 0.3]

                                # Ingest document
                                await qdrant_service.ingest_document(
                                    doc_id="test_doc",
                                    content="test content",
                                    collection_name="test_collection"
                                )

                                # Verify upsert was called
                                mock_client.upsert.assert_called_once()

                                # Clean up
                                await qdrant_service.close()
                                await embedding_service.close()


class TestMemoryPipelineValidation:
    """Test validation and error handling in memory pipeline."""

    @pytest.mark.asyncio
    async def test_qdrant_service_error_handling(self):
        """Test QdrantService handles errors gracefully."""
        with patch('memory.qdrant.QDRANT_AVAILABLE', True):
            with patch('memory.qdrant.SENTENCE_TRANSFORMERS_AVAILABLE', True):
                with patch('memory.qdrant.SentenceTransformer') as mock_st:
                    mock_model = Mock()
                    mock_model.encode.return_value = Mock()
                    mock_model.encode.return_value.tolist.return_value = [0.1, 0.2, 0.3]
                    mock_st.return_value = mock_model

                    # Mock client that raises an exception
                    mock_client = AsyncMock()
                    mock_client.search = AsyncMock(side_effect=Exception("Qdrant error"))

                    with patch('memory.qdrant.AsyncQdrantClient', return_value=mock_client):
                        service = QdrantService()

                        # fetch_context_for_director should return empty context on error
                        context = await service.fetch_context_for_director(
                            chapter_seed="test",
                            active_characters=["test"]
                        )

                        assert isinstance(context, ContextRetrievalResult)
                        assert len(context.spotlight_context) == 0
                        assert len(context.ambient_echo) == 0

    @pytest.mark.asyncio
    async def test_embedding_service_error_handling(self):
        """Test EmbeddingService handles errors gracefully."""
        with patch('memory.embedding_service.SENTENCE_TRANSFORMERS_AVAILABLE', True):
            with patch('memory.embedding_service.SentenceTransformer') as mock_st:
                mock_model = Mock()
                mock_model.encode.side_effect = Exception("Embedding error")
                mock_st.return_value = mock_model

                service = EmbeddingService(provider="local")

                with pytest.raises(Exception, match="Embedding error"):
                    await service.generate_embedding("test")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
