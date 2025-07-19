"""
Embedding service with multiple provider support including Jina AI.
Provides unified interface for generating text embeddings.
"""

import asyncio
import logging
import os
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Optional


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

from pydantic import BaseModel, Field


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


@dataclass
class ChunkMetadata:
    """Metadata for text chunks in late chunking."""
    chunk_id: str
    original_index: int
    start_char: int
    end_char: int
    token_count: int
    content_hash: str
    overlap_with_previous: int = 0
    overlap_with_next: int = 0


class BulkProcessingProgress(BaseModel):
    """Progress tracking for bulk operations."""
    total_items: int = Field(description="Total number of items to process")
    processed_items: int = Field(default=0, description="Number of items processed")
    failed_items: int = Field(default=0, description="Number of items that failed")
    current_batch: int = Field(default=0, description="Current batch number")
    total_batches: int = Field(description="Total number of batches")
    processing_time: float = Field(default=0.0, description="Total processing time in seconds")
    estimated_time_remaining: float = Field(default=0.0, description="Estimated time remaining in seconds")
    throughput_items_per_second: float = Field(default=0.0, description="Processing throughput")
    error_messages: list[str] = Field(default_factory=list, description="Error messages encountered")

    @property
    def progress_percentage(self) -> float:
        """Calculate progress percentage."""
        if self.total_items == 0:
            return 0.0
        return (self.processed_items / self.total_items) * 100.0

    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        completed = self.processed_items + self.failed_items
        if completed == 0:
            return 0.0
        return (self.processed_items / completed) * 100.0


class BulkEmbeddingResult(BaseModel):
    """Result of bulk embedding operation."""
    embeddings: list[list[float]] = Field(description="Generated embeddings")
    metadata: list[dict[str, Any]] = Field(default_factory=list, description="Metadata for each embedding")
    failed_indices: list[int] = Field(default_factory=list, description="Indices of failed items")
    processing_stats: dict[str, Any] = Field(default_factory=dict, description="Processing statistics")
    total_tokens_used: int = Field(default=0, description="Total tokens consumed")
    estimated_cost: float = Field(default=0.0, description="Estimated cost in USD")
    chunk_mappings: Optional[list[list[ChunkMetadata]]] = Field(default=None, description="Chunk metadata for late chunking")


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
    def get_max_context_length(self) -> int:
        """Return maximum context length for this provider."""
        pass

    @abstractmethod
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text."""
        pass

    @abstractmethod
    def calculate_cost(self, token_count: int) -> float:
        """Calculate estimated cost for token count."""
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

    def get_max_context_length(self) -> int:
        """Return maximum context length for local models."""
        context_map = {
            "all-MiniLM-L6-v2": 256,
            "all-mpnet-base-v2": 384,
            "all-MiniLM-L12-v2": 256,
        }
        return context_map.get(self.model_name, 256)

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count (approximate for local models)."""
        # Rough estimation: ~4 characters per token for English
        return len(text) // 4

    def calculate_cost(self, token_count: int) -> float:
        """Local models have no cost."""
        return 0.0

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
            "jina-embeddings-v4": 2048,  # CORRECT: Jina v4 outputs 2048-dimensional vectors
            "jina-embeddings-v3": 1024,
            "jina-embeddings-v2-base-en": 768,
        }
        return dimension_map.get(self.model, 2048)

    def get_max_context_length(self) -> int:
        """Return maximum context length for Jina models."""
        context_map = {
            "jina-embeddings-v4": 32768,  # 32K context window for v4
            "jina-embeddings-v3": 8192,
            "jina-embeddings-v2-base-en": 8192,
        }
        return context_map.get(self.model, 8192)

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count using Jina's approximation."""
        # Jina uses approximately 3.5-4 characters per token
        return len(text) // 4

    def calculate_cost(self, token_count: int) -> float:
        """Calculate estimated cost for Jina embeddings."""
        # Jina v4 pricing: approximately $0.02 per million tokens
        cost_per_million_tokens = 0.02
        return (token_count / 1_000_000) * cost_per_million_tokens

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

    def get_max_context_length(self) -> int:
        """Return maximum context length for OpenAI models."""
        context_map = {
            "text-embedding-3-large": 8191,
            "text-embedding-3-small": 8191,
            "text-embedding-ada-002": 8191,
        }
        return context_map.get(self.model, 8191)

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count using OpenAI's approximation."""
        # OpenAI uses approximately 4 characters per token
        return len(text) // 4

    def calculate_cost(self, token_count: int) -> float:
        """Calculate estimated cost for OpenAI embeddings."""
        # OpenAI text-embedding-3-large: $0.13 per million tokens
        # OpenAI text-embedding-3-small: $0.02 per million tokens
        cost_map = {
            "text-embedding-3-large": 0.13,
            "text-embedding-3-small": 0.02,
            "text-embedding-ada-002": 0.10,
        }
        cost_per_million_tokens = cost_map.get(self.model, 0.10)
        return (token_count / 1_000_000) * cost_per_million_tokens

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

    def _smart_text_chunker(
        self,
        text: str,
        max_tokens: int,
        overlap_tokens: int = 50,
        preserve_sentences: bool = True
    ) -> list[tuple[str, ChunkMetadata]]:
        """Smart text chunking with sentence preservation and overlap."""
        if not text.strip():
            return []

        # If text is within limits, return as single chunk
        estimated_tokens = self.provider.estimate_tokens(text)
        if estimated_tokens <= max_tokens:
            metadata = ChunkMetadata(
                chunk_id="chunk_0",
                original_index=0,
                start_char=0,
                end_char=len(text),
                token_count=estimated_tokens,
                content_hash=self._generate_content_hash(text)
            )
            return [(text, metadata)]

        chunks = []
        sentences = self._split_into_sentences(text) if preserve_sentences else [text]

        current_chunk = ""
        current_start = 0
        chunk_index = 0

        for sentence in sentences:
            # Check if adding this sentence would exceed token limit
            potential_chunk = current_chunk + (" " if current_chunk else "") + sentence
            potential_tokens = self.provider.estimate_tokens(potential_chunk)

            if potential_tokens > max_tokens and current_chunk:
                # Save current chunk and start new one
                chunk_end = current_start + len(current_chunk)
                metadata = ChunkMetadata(
                    chunk_id=f"chunk_{chunk_index}",
                    original_index=chunk_index,
                    start_char=current_start,
                    end_char=chunk_end,
                    token_count=self.provider.estimate_tokens(current_chunk),
                    content_hash=self._generate_content_hash(current_chunk)
                )
                chunks.append((current_chunk, metadata))

                # Start new chunk with overlap if specified
                if overlap_tokens > 0 and chunks:
                    overlap_text = self._get_overlap_text(current_chunk, overlap_tokens)
                    current_chunk = overlap_text + " " + sentence
                    current_start = chunk_end - len(overlap_text)
                    metadata.overlap_with_next = len(overlap_text)
                else:
                    current_chunk = sentence
                    current_start = chunk_end

                chunk_index += 1
            else:
                current_chunk = potential_chunk

        # Add final chunk if any content remains
        if current_chunk.strip():
            chunk_end = current_start + len(current_chunk)
            metadata = ChunkMetadata(
                chunk_id=f"chunk_{chunk_index}",
                original_index=chunk_index,
                start_char=current_start,
                end_char=chunk_end,
                token_count=self.provider.estimate_tokens(current_chunk),
                content_hash=self._generate_content_hash(current_chunk)
            )
            chunks.append((current_chunk, metadata))

        return chunks

    def _split_into_sentences(self, text: str) -> list[str]:
        """Split text into sentences using regex patterns."""
        # Simple sentence splitting pattern that works reliably
        # Split on sentence endings followed by whitespace and capital letter or quote
        pattern = r'(?<=[.!?])\s+(?=[A-Z"\']|$)'

        sentences = re.split(pattern, text)
        return [s.strip() for s in sentences if s.strip()]

    def _get_overlap_text(self, text: str, overlap_tokens: int) -> str:
        """Extract overlap text from the end of current chunk."""
        words = text.split()
        # Approximate: take last N words where N ~= overlap_tokens
        overlap_words = max(1, overlap_tokens // 4)  # Rough token-to-word ratio
        return " ".join(words[-overlap_words:]) if len(words) > overlap_words else text

    def _generate_content_hash(self, content: str) -> str:
        """Generate a hash for content (simplified version)."""
        import hashlib
        return hashlib.md5(content.encode()).hexdigest()[:16]

    async def bulk_process_with_chunking(
        self,
        texts: list[str],
        max_chunk_tokens: Optional[int] = None,
        chunk_overlap: int = 50,
        batch_size: int = 50,
        progress_callback: Optional[Callable[[BulkProcessingProgress], None]] = None,
        preserve_sentences: bool = True
    ) -> BulkEmbeddingResult:
        """Process texts with automatic chunking for large documents."""
        start_time = time.time()

        # Use provider's max context or specified limit
        if max_chunk_tokens is None:
            max_chunk_tokens = self.provider.get_max_context_length() - 100  # Safety buffer

        # Phase 1: Chunk all texts
        all_chunks = []
        chunk_mappings = []
        total_tokens = 0

        for i, text in enumerate(texts):
            text_chunks = self._smart_text_chunker(
                text, max_chunk_tokens, chunk_overlap, preserve_sentences
            )

            chunk_data = []
            for chunk_text, metadata in text_chunks:
                all_chunks.append(chunk_text)
                chunk_data.append(metadata)
                total_tokens += metadata.token_count

            chunk_mappings.append(chunk_data)

            # Update progress for chunking phase
            if progress_callback:
                progress = BulkProcessingProgress(
                    total_items=len(texts),
                    processed_items=i + 1,
                    total_batches=1,
                    current_batch=1,
                    processing_time=time.time() - start_time
                )
                progress_callback(progress)

        logger.info(f"Chunked {len(texts)} texts into {len(all_chunks)} chunks")

        # Phase 2: Process chunks in batches
        total_batches = (len(all_chunks) + batch_size - 1) // batch_size
        all_embeddings = []
        failed_indices = []
        error_messages = []

        for batch_idx in range(total_batches):
            batch_start = batch_idx * batch_size
            batch_end = min(batch_start + batch_size, len(all_chunks))
            batch_chunks = all_chunks[batch_start:batch_end]

            try:
                batch_embeddings = await self.generate_embeddings(batch_chunks)
                all_embeddings.extend(batch_embeddings)

                # Small delay between batches for rate limiting
                if batch_idx < total_batches - 1:
                    await asyncio.sleep(0.1)

            except Exception as e:
                logger.error(f"Batch {batch_idx + 1} failed: {e}")
                error_messages.append(f"Batch {batch_idx + 1}: {str(e)}")

                # Add failed indices
                for i in range(batch_start, batch_end):
                    failed_indices.append(i)

                # Add placeholder embeddings for failed chunks
                embedding_dim = self.get_embedding_dimension()
                for _ in range(len(batch_chunks)):
                    all_embeddings.append([0.0] * embedding_dim)

            # Update progress
            if progress_callback:
                current_time = time.time()
                processing_time = current_time - start_time
                processed_chunks = batch_end

                # Calculate ETA
                if processed_chunks > 0:
                    throughput = processed_chunks / processing_time
                    remaining_chunks = len(all_chunks) - processed_chunks
                    eta = remaining_chunks / throughput if throughput > 0 else 0
                else:
                    eta = 0
                    throughput = 0

                progress = BulkProcessingProgress(
                    total_items=len(all_chunks),
                    processed_items=processed_chunks,
                    failed_items=len(failed_indices),
                    current_batch=batch_idx + 1,
                    total_batches=total_batches,
                    processing_time=processing_time,
                    estimated_time_remaining=eta,
                    throughput_items_per_second=throughput,
                    error_messages=error_messages
                )
                progress_callback(progress)

        # Phase 3: Reassemble embeddings by original text
        final_embeddings = []
        final_metadata = []

        chunk_idx = 0
        for text_idx, text_chunk_data in enumerate(chunk_mappings):
            text_embeddings = []
            text_metadata = {
                "original_text_index": text_idx,
                "chunk_count": len(text_chunk_data),
                "total_tokens": sum(chunk.token_count for chunk in text_chunk_data),
                "chunks": text_chunk_data
            }

            for _chunk_meta in text_chunk_data:
                if chunk_idx < len(all_embeddings):
                    text_embeddings.append(all_embeddings[chunk_idx])
                chunk_idx += 1

            # For multi-chunk texts, you might want to average embeddings
            # or use other combination strategies
            if len(text_embeddings) == 1:
                final_embeddings.append(text_embeddings[0])
            elif len(text_embeddings) > 1:
                # Average the embeddings (you could implement other strategies)
                avg_embedding = [
                    sum(emb[i] for emb in text_embeddings) / len(text_embeddings)
                    for i in range(len(text_embeddings[0]))
                ]
                final_embeddings.append(avg_embedding)
                text_metadata["combination_method"] = "average"
            else:
                # No embeddings available (all failed)
                embedding_dim = self.get_embedding_dimension()
                final_embeddings.append([0.0] * embedding_dim)
                text_metadata["embedding_failed"] = True

            final_metadata.append(text_metadata)

        # Calculate final statistics
        processing_time = time.time() - start_time
        estimated_cost = self.provider.calculate_cost(total_tokens)

        processing_stats = {
            "total_processing_time": processing_time,
            "total_chunks_created": len(all_chunks),
            "chunks_per_text_avg": len(all_chunks) / len(texts) if texts else 0,
            "total_batches_processed": total_batches,
            "average_batch_time": processing_time / total_batches if total_batches > 0 else 0,
            "success_rate": (len(all_chunks) - len(failed_indices)) / len(all_chunks) * 100 if all_chunks else 0,
            "throughput_chunks_per_second": len(all_chunks) / processing_time if processing_time > 0 else 0
        }

        return BulkEmbeddingResult(
            embeddings=final_embeddings,
            metadata=final_metadata,
            failed_indices=failed_indices,
            processing_stats=processing_stats,
            total_tokens_used=total_tokens,
            estimated_cost=estimated_cost,
            chunk_mappings=chunk_mappings
        )

    async def bulk_process_materials(
        self,
        material_contents: list[str],
        material_ids: Optional[list[str]] = None,
        batch_size: int = 50,
        enable_late_chunking: bool = True,
        max_chunk_tokens: Optional[int] = None,
        progress_callback: Optional[Callable[[BulkProcessingProgress], None]] = None
    ) -> BulkEmbeddingResult:
        """Specialized bulk processing for material ingestion."""

        if material_ids and len(material_ids) != len(material_contents):
            raise ValueError("material_ids length must match material_contents length")

        if not material_ids:
            material_ids = [f"material_{i}" for i in range(len(material_contents))]

        # Add material IDs to each text for tracking
        annotated_contents = []
        for i, content in enumerate(material_contents):
            # Prepend material ID as context (will be removed after embedding)
            annotated_content = f"[Material ID: {material_ids[i]}]\n{content}"
            annotated_contents.append(annotated_content)

        if enable_late_chunking:
            return await self.bulk_process_with_chunking(
                texts=annotated_contents,
                max_chunk_tokens=max_chunk_tokens,
                batch_size=batch_size,
                progress_callback=progress_callback,
                preserve_sentences=True
            )
        else:
            # Process without chunking (original batch_process logic)
            start_time = time.time()
            all_embeddings = await self.batch_process(
                texts=annotated_contents,
                batch_size=batch_size
            )

            processing_time = time.time() - start_time
            total_tokens = sum(self.provider.estimate_tokens(text) for text in annotated_contents)
            estimated_cost = self.provider.calculate_cost(total_tokens)

            metadata = [
                {
                    "material_id": material_ids[i],
                    "original_text_index": i,
                    "chunk_count": 1,
                    "total_tokens": self.provider.estimate_tokens(content),
                    "chunking_enabled": False
                }
                for i, content in enumerate(annotated_contents)
            ]

            processing_stats = {
                "total_processing_time": processing_time,
                "total_chunks_created": len(annotated_contents),
                "chunks_per_text_avg": 1.0,
                "total_batches_processed": (len(annotated_contents) + batch_size - 1) // batch_size,
                "success_rate": 100.0,  # Assuming no failures in simple mode
                "throughput_chunks_per_second": len(annotated_contents) / processing_time if processing_time > 0 else 0
            }

            return BulkEmbeddingResult(
                embeddings=all_embeddings,
                metadata=metadata,
                failed_indices=[],
                processing_stats=processing_stats,
                total_tokens_used=total_tokens,
                estimated_cost=estimated_cost
            )

    def get_chunking_recommendations(self, texts: list[str]) -> dict[str, Any]:
        """Analyze texts and provide chunking recommendations."""
        if not texts:
            return {"recommendation": "no_chunking", "reason": "No texts provided"}

        max_context = self.provider.get_max_context_length()
        total_tokens = 0
        oversized_count = 0
        token_stats = []

        for text in texts:
            tokens = self.provider.estimate_tokens(text)
            total_tokens += tokens
            token_stats.append(tokens)

            if tokens > max_context:
                oversized_count += 1

        avg_tokens = total_tokens / len(texts) if texts else 0
        max_tokens = max(token_stats) if token_stats else 0
        oversized_percentage = (oversized_count / len(texts)) * 100

        # Recommendation logic
        if oversized_count == 0:
            recommendation = "no_chunking"
            reason = "All texts fit within context window"
        elif oversized_percentage < 10:
            recommendation = "selective_chunking"
            reason = f"Only {oversized_percentage:.1f}% of texts exceed context limit"
        else:
            recommendation = "bulk_chunking"
            reason = f"{oversized_percentage:.1f}% of texts exceed context limit"

        # Suggest optimal chunk size
        suggested_chunk_size = min(max_context - 100, max(2048, max_context // 2))

        return {
            "recommendation": recommendation,
            "reason": reason,
            "statistics": {
                "total_texts": len(texts),
                "total_tokens": total_tokens,
                "average_tokens": avg_tokens,
                "max_tokens": max_tokens,
                "oversized_count": oversized_count,
                "oversized_percentage": oversized_percentage,
                "provider_max_context": max_context
            },
            "suggestions": {
                "chunk_size": suggested_chunk_size,
                "chunk_overlap": 50,
                "preserve_sentences": True,
                "batch_size": min(50, len(texts))
            }
        }

    async def close(self) -> None:
        """Close the embedding provider."""
        await self.provider.close()


async def main():
    """Example usage of EmbeddingService with bulk operations and late chunking."""
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

    # Test Jina provider with bulk operations (if API key available)
    jina_api_key = os.getenv("JINA_API_KEY")
    if jina_api_key:
        print("\nTesting Jina AI provider with bulk operations...")
        jina_service = EmbeddingService(provider="jina", api_key=jina_api_key)

        try:
            # Test basic embeddings
            texts = ["Hello from Jina", "Testing Jina AI embeddings"]
            embeddings = await jina_service.generate_embeddings(texts)
            print(f"Jina generated {len(embeddings)} embeddings with dimension {len(embeddings[0])}")

            # Test chunking recommendations
            long_texts = [
                "This is a short text.",
                "This is a much longer text that might exceed the context window limits of some embedding models. " * 50,
                "Another moderately long text that contains multiple sentences and complex information."
            ]

            recommendations = jina_service.get_chunking_recommendations(long_texts)
            print(f"\nChunking recommendations: {recommendations['recommendation']}")
            print(f"Reason: {recommendations['reason']}")
            print(f"Statistics: {recommendations['statistics']}")

            # Test bulk processing with chunking
            print("\nTesting bulk processing with late chunking...")

            def progress_callback(progress: BulkProcessingProgress):
                print(f"Progress: {progress.progress_percentage:.1f}% "
                      f"({progress.processed_items}/{progress.total_items}) "
                      f"- Batch {progress.current_batch}/{progress.total_batches}")
                if progress.throughput_items_per_second > 0:
                    print(f"Throughput: {progress.throughput_items_per_second:.2f} items/sec")

            bulk_result = await jina_service.bulk_process_with_chunking(
                texts=long_texts,
                batch_size=2,
                progress_callback=progress_callback,
                preserve_sentences=True
            )

            print("\nBulk processing results:")
            print(f"Generated {len(bulk_result.embeddings)} embeddings")
            print(f"Total tokens used: {bulk_result.total_tokens_used}")
            print(f"Estimated cost: ${bulk_result.estimated_cost:.4f}")
            print(f"Processing stats: {bulk_result.processing_stats}")

            # Test material-specific bulk processing
            print("\nTesting material ingestion processing...")
            material_contents = [
                "Character: John is a brave knight with a noble heart.",
                "Setting: The ancient castle stands on a hill overlooking the valley.",
                "Plot: The dragon has been terrorizing the village for months."
            ]
            material_ids = ["char_001", "setting_001", "plot_001"]

            material_result = await jina_service.bulk_process_materials(
                material_contents=material_contents,
                material_ids=material_ids,
                enable_late_chunking=True,
                batch_size=2
            )

            print("\nMaterial processing results:")
            print(f"Generated embeddings for {len(material_result.embeddings)} materials")
            print(f"Total tokens: {material_result.total_tokens_used}")
            print(f"Success rate: {material_result.processing_stats.get('success_rate', 0):.1f}%")

            # Print sample metadata
            if material_result.metadata:
                print(f"Sample metadata: {material_result.metadata[0]}")

        except Exception as e:
            print(f"Jina test failed: {e}")
        finally:
            await jina_service.close()
    else:
        print("\nSkipping Jina AI test (no API key)")


if __name__ == "__main__":
    asyncio.run(main())
