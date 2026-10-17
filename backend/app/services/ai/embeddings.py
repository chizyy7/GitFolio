"""
Embedding service.

Wraps Ollama's embedding endpoint with batching, a query cache and clear
errors.  Documents are embedded with the same model as queries — mixing models
would silently destroy retrieval quality.
"""

from __future__ import annotations

import hashlib
import threading
from functools import lru_cache

from app.core.config import settings
from app.core.logging import get_logger
from app.services.llm import OllamaClient, OllamaUnavailable, get_ollama

logger = get_logger("embeddings")


class EmbeddingService:
    """Batched embedding helper around a shared ``OllamaClient``."""

    def __init__(self, client: OllamaClient | None = None, batch_size: int | None = None) -> None:
        self.client = client or get_ollama()
        self.batch_size = batch_size or settings.EMBED_BATCH_SIZE
        self._cache: dict[str, list[float]] = {}
        self._cache_lock = threading.Lock()
        self._max_cache = 512
        self._dimension: int | None = None

    # ------------------------------------------------------------ documents
    def embed_documents(self, texts: list[str], *, progress_every: int = 0) -> list[list[float]]:
        """Embed many texts, batching requests to keep memory predictable."""
        if not texts:
            return []

        vectors: list[list[float]] = []
        total = len(texts)

        for start in range(0, total, self.batch_size):
            batch = texts[start : start + self.batch_size]
            vectors.extend(self.client.embed(batch))
            if progress_every and (start // self.batch_size) % progress_every == 0:
                logger.info("Embedded %d/%d chunks", min(start + len(batch), total), total)

        if vectors and self._dimension is None:
            self._dimension = len(vectors[0])
            logger.debug("Embedding dimension: %d", self._dimension)
        return vectors

    # ---------------------------------------------------------------- query
    def embed_query(self, text: str) -> list[float]:
        """Embed a search query, memoised by content hash."""
        key = hashlib.sha256(text.encode("utf-8")).hexdigest()

        with self._cache_lock:
            cached = self._cache.get(key)
        if cached is not None:
            return cached

        vector = self.client.embed_one(text)

        with self._cache_lock:
            if len(self._cache) >= self._max_cache:
                # Cheap eviction: drop the oldest-ish entry.
                self._cache.pop(next(iter(self._cache)))
            self._cache[key] = vector
        return vector

    # ------------------------------------------------------------- helpers
    @property
    def dimension(self) -> int | None:
        """Embedding width, computed on first use."""
        if self._dimension is None:
            try:
                self._dimension = len(self.embed_query("dimension probe"))
            except OllamaUnavailable:
                return None
        return self._dimension

    @property
    def model_name(self) -> str:
        return self.client.embed_model


@lru_cache(maxsize=1)
def get_embedding_service() -> EmbeddingService:
    """Process-wide embedding service singleton."""
    return EmbeddingService()


__all__ = ["EmbeddingService", "get_embedding_service"]
