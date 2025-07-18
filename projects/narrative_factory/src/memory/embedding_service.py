"""
Embedding service with multiple provider support including Jina AI.
Provides unified interface for generating text embeddings.
"""

import asyncio
import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Optional


try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

try:
    from tenacity import retry, stop_after_attempt, wait_exponential
    TENACITY_AVAILABLE = True
except ImportError:
    TENACITY_AVAILABLE = False

# Lazy import sentence_transformers to avoid bus error during testing
SENTENCE_TRANSFORMERS_AVAILABLE = None

def _check_sentence_transformers():
    """Lazy check for sentence_transformers availability."""
    global SENTENCE_TRANSFORMERS_AVAILABLE
    if SENTENCE_TRANSFORMERS_AVAILABLE is None:
        try:
            import importlib.util
            spec = importlib.util.find_spec("sentence_transformers")
            SENTENCE_TRANSFORMERS_AVAILABLE = spec is not None
        except ImportError:
            SENTENCE_TRANSFORMERS_AVAILABLE = False
    return SENTENCE_TRANSFORMERS_AVAILABLE

from pydantic import BaseModel


logger = logging.getLogger(__name__)


class JinaEmbeddingRequest(BaseModel):
    """Jina AI embedding request model."""
    model: str = "jina-embeddings-v4"
    task: str = "text-matching"
    input: list[dict[str, str]]


class JinaEmbeddingResponse(BaseModel):
    """Jina AI embedding response model."""
    data: list[dict[str, Any]]
    model: str
    usage: dict[str, int]


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""

    @abstractmethod
    async def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts."""
        pass

    @abstractmethod
    def get_embedding_dimension(self) -> int:
        """Return the embedding dimension for this provider."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Clean up resources."""
        pass


class LocalSentenceTransformersProvider(EmbeddingProvider):
    """Local embedding provider using sentence-transformers."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        if not _check_sentence_transformers():
            raise ImportError("sentence-transformers is required. Install with: pip install sentence-transformers")

        self.model_name = model_name
        self._model = None

    async def _get_model(self):
        """Lazy load the model."""
        if self._model is None:
            if not _check_sentence_transformers():
                raise RuntimeError("sentence-transformers not available")
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
        return self._model

    async def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings using local sentence-transformers model."""
        if not texts:
            raise ValueError("Input texts cannot be empty")

        try:
            model = await self._get_model()
            embeddings = model.encode(texts)
            return embeddings.tolist()
        except Exception as e:
            logger.error(f"Local embedding generation failed: {e}")
            raise

    def get_embedding_dimension(self) -> int:
        """Return embedding dimension (384 for all-MiniLM-L6-v2)."""
        dimension_map = {
            "all-MiniLM-L6-v2": 384,
            "all-mpnet-base-v2": 768,
            "all-MiniLM-L12-v2": 384,
        }
        return dimension_map.get(self.model_name, 384)

    async def close(self) -> None:
        """No cleanup needed for local models."""
        pass


class JinaEmbeddingProvider(EmbeddingProvider):
    """Jina AI embedding provider."""

    def __init__(self, api_key: Optional[str] = None, model: str = "jina-embeddings-v4"):
        if not HTTPX_AVAILABLE:
            raise ImportError("httpx is required for Jina AI. Install with: pip install httpx")

        if not TENACITY_AVAILABLE:
            raise ImportError("tenacity is required for Jina AI. Install with: pip install tenacity")

        self.api_key = api_key or os.getenv("JINA_API_KEY")
        if not self.api_key:
            raise ValueError("JINA_API_KEY environment variable or api_key parameter required")

        self.model = model
        self.client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
                "Content-Type": "application/json"
            },
            timeout=60.0
        )

    def get_embedding_dimension(self) -> int:
        """Return embedding dimension for Jina models."""
        dimension_map = {
            "jina-embeddings-v4": 2048,
            "jina-embeddings-v3": 1024,
            "jina-embeddings-v2-base-en": 768,
        }
        return dimension_map.get(self.model, 2048)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10)
    ) if TENACITY_AVAILABLE else lambda x: x
    async def generate_embeddings(
        self,
        texts: list[str],
        task: str = "text-matching"
    ) -> list[list[float]]:
        """Generate embeddings using Jina AI API."""
        if not texts:
            raise ValueError("Input texts cannot be empty")

        if not all(isinstance(text, str) for text in texts):
            raise ValueError("All inputs must be strings")

        try:
            request_data = JinaEmbeddingRequest(
                model=self.model,
                task=task,
                input=[{"text": text} for text in texts]
            )

            response = await self.client.post(
                "https://api.jina.ai/v1/embeddings",
                json=request_data.model_dump()
            )
            response.raise_for_status()

            response_data = JinaEmbeddingResponse(**response.json())
            embeddings = [item["embedding"] for item in response_data.data]

            logger.info(f"Generated {len(embeddings)} embeddings using Jina AI")
            return embeddings

        except httpx.HTTPError as e:
            logger.error(f"Jina API request failed: {e}")
            raise RuntimeError(f"Jina API request failed: {e}") from e
        except Exception as e:
            logger.error(f"Jina embedding generation failed: {e}")
            raise RuntimeError(f"Embedding generation failed: {e}") from e

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI embedding provider (placeholder implementation)."""

    def __init__(self, api_key: Optional[str] = None, model: str = "text-embedding-3-large"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable or api_key parameter required")

        self.model = model
        # Note: Full OpenAI implementation would require openai package

    def get_embedding_dimension(self) -> int:
        """Return embedding dimension for OpenAI models."""
        dimension_map = {
            "text-embedding-3-large": 3072,
            "text-embedding-3-small": 1536,
            "text-embedding-ada-002": 1536,
        }
        return dimension_map.get(self.model, 1536)

    async def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings using OpenAI API."""
        # Placeholder - would require OpenAI client implementation
        raise NotImplementedError("OpenAI embedding provider not yet implemented")

    async def close(self) -> None:
        """Close the client."""
        pass


class EmbeddingService:
    """Unified embedding service with multiple provider support."""

    def __init__(self, provider: str = "local", **provider_kwargs):
        """
        Initialize embedding service with specified provider.

        Args:
            provider: Provider type ("local", "jina", "openai")
            **provider_kwargs: Arguments passed to provider constructor
        """
        self.provider_name = provider
        self.provider = self._create_provider(provider, **provider_kwargs)

    def _create_provider(self, provider: str, **kwargs) -> EmbeddingProvider:
        """Create the specified embedding provider."""
        if provider == "local":
            return LocalSentenceTransformersProvider(**kwargs)
        elif provider == "jina":
            return JinaEmbeddingProvider(**kwargs)
        elif provider == "openai":
            return OpenAIEmbeddingProvider(**kwargs)
        else:
            raise ValueError(f"Unknown provider: {provider}")

    def get_embedding_dimension(self) -> int:
        """Return embedding dimension for the current provider."""
        return self.provider.get_embedding_dimension()

    async def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors
        """
        return await self.provider.generate_embeddings(texts)

    async def generate_embedding(self, text: str) -> list[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text string to embed

        Returns:
            Embedding vector
        """
        embeddings = await self.generate_embeddings([text])
        return embeddings[0]

    async def batch_process(
        self,
        texts: list[str],
        batch_size: int = 100,
        delay_between_batches: float = 0.1
    ) -> list[list[float]]:
        """
        Process texts in batches to handle rate limits.

        Args:
            texts: List of texts to process
            batch_size: Size of each batch
            delay_between_batches: Delay in seconds between batches

        Returns:
            List of all embeddings
        """
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_embeddings = await self.generate_embeddings(batch)
            all_embeddings.extend(batch_embeddings)

            # Add delay between batches for rate limiting
            if i + batch_size < len(texts):
                await asyncio.sleep(delay_between_batches)

            logger.info(f"Processed batch {i//batch_size + 1}/{(len(texts) + batch_size - 1)//batch_size}")

        return all_embeddings

    async def close(self) -> None:
        """Close the embedding provider."""
        await self.provider.close()


async def main():
    """Example usage of EmbeddingService."""
    # Test local provider
    print("Testing local provider...")
    local_service = EmbeddingService(provider="local")

    try:
        texts = ["Hello world", "This is a test", "Embedding generation"]
        embeddings = await local_service.generate_embeddings(texts)
        print(f"Generated {len(embeddings)} embeddings with dimension {len(embeddings[0])}")

        # Test single embedding
        single_embedding = await local_service.generate_embedding("Single text test")
        print(f"Single embedding dimension: {len(single_embedding)}")

    finally:
        await local_service.close()

    # Test Jina provider (if API key available)
    jina_api_key = os.getenv("JINA_API_KEY")
    if jina_api_key:
        print("\nTesting Jina AI provider...")
        jina_service = EmbeddingService(provider="jina", api_key=jina_api_key)

        try:
            texts = ["Hello from Jina", "Testing Jina AI embeddings"]
            embeddings = await jina_service.generate_embeddings(texts)
            print(f"Jina generated {len(embeddings)} embeddings with dimension {len(embeddings[0])}")

        except Exception as e:
            print(f"Jina test failed: {e}")
        finally:
            await jina_service.close()
    else:
        print("\nSkipping Jina AI test (no API key)")


if __name__ == "__main__":
    asyncio.run(main())
