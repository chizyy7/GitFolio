"""
ChromaDB vector-store wrapper.

One Chroma collection per repository (``repo_<uuid-hex>``).  Embeddings are
produced by Ollama (``nomic-embed-text``) and always passed in explicitly so
Chroma never has to reach out to an embedding function of its own.
"""

from __future__ import annotations

import threading
from functools import lru_cache
from typing import Any, Sequence

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("vectorstore")


class VectorStoreUnavailable(RuntimeError):
    """Raised when ChromaDB cannot be reached or is disabled."""


def collection_name(repo_id: str) -> str:
    """
    Deterministic, Chroma-legal collection name for a repository.

    Chroma requires 3-63 chars of ``[a-zA-Z0-9_-]`` beginning/ending alnum.
    """
    safe = str(repo_id).replace("-", "")
    return f"repo_{safe}"[:63]


class VectorStore:
    """Thread-safe lazy handle on a ChromaDB HTTP deployment."""

    def __init__(self) -> None:
        self._client: Any | None = None
        self._lock = threading.Lock()

    # ----------------------------------------------------------- plumbing
    @property
    def enabled(self) -> bool:
        return settings.CHROMA_ENABLED

    def _connect(self) -> Any:
        if not self.enabled:
            raise VectorStoreUnavailable(
                "ChromaDB is disabled (CHROMA_ENABLED=false). "
                "Start the `chroma` service or set CHROMA_ENABLED=true."
            )
        with self._lock:
            if self._client is None:
                try:
                    import chromadb
                    from chromadb.config import Settings as ChromaSettings
                except ImportError as exc:  # pragma: no cover
                    raise VectorStoreUnavailable(
                        "chromadb-client is not installed. `pip install chromadb-client`."
                    ) from exc

                try:
                    if settings.CHROMA_HOST in ("localhost", "127.0.0.1") and settings.CHROMA_PORT == 0:
                        # Embedded/persistent mode (single-node deployments).
                        self._client = chromadb.PersistentClient(
                            path=str(settings.STORAGE_PATH / "chroma"),
                            settings=ChromaSettings(anonymized_telemetry=False),
                        )
                    else:
                        headers = (
                            {"Authorization": f"Bearer {settings.CHROMA_AUTH_TOKEN}"}
                            if settings.CHROMA_AUTH_TOKEN
                            else None
                        )
                        self._client = chromadb.HttpClient(
                            host=settings.CHROMA_HOST,
                            port=settings.CHROMA_PORT,
                            ssl=settings.CHROMA_SSL,
                            headers=headers,
                            settings=ChromaSettings(anonymized_telemetry=False),
                        )
                    logger.info(
                        "Connected to ChromaDB at %s:%s", settings.CHROMA_HOST, settings.CHROMA_PORT
                    )
                except Exception as exc:
                    self._client = None
                    raise VectorStoreUnavailable(f"Could not connect to ChromaDB: {exc}") from exc
            return self._client

    # --------------------------------------------------------- collections
    def get_collection(self, repo_id: str, create: bool = True) -> Any:
        """Fetch (or create) the collection backing one repository."""
        client = self._connect()
        name = collection_name(repo_id)
        try:
            if create:
                return client.get_or_create_collection(
                    name=name,
                    # Cosine distance suits normalised text embeddings well.
                    metadata={"hnsw:space": "cosine", "repo_id": str(repo_id)},
                )
            return client.get_collection(name=name)
        except Exception as exc:
            raise VectorStoreUnavailable(f"ChromaDB collection error for {name}: {exc}") from exc

    def collection_exists(self, repo_id: str) -> bool:
        try:
            client = self._connect()
            client.get_collection(collection_name(repo_id))
            return True
        except Exception:
            return False

    # --------------------------------------------------------------- write
    def upsert(
        self,
        repo_id: str,
        *,
        ids: Sequence[str],
        documents: Sequence[str],
        metadatas: Sequence[dict[str, Any]],
        embeddings: Sequence[Sequence[float]],
    ) -> int:
        """Insert/update embedded chunks. Returns the number written."""
        if not ids:
            return 0
        collection = self.get_collection(repo_id, create=True)
        collection.upsert(
            ids=list(ids),
            documents=list(documents),
            metadatas=[_clean_metadata(m) for m in metadatas],
            embeddings=[list(map(float, vec)) for vec in embeddings],
        )
        return len(ids)

    def delete_where(self, repo_id: str, where: dict[str, Any]) -> None:
        """Delete chunks matching a metadata filter (e.g. one file)."""
        try:
            collection = self.get_collection(repo_id, create=False)
            collection.delete(where=where)
        except VectorStoreUnavailable:
            raise
        except Exception as exc:
            logger.warning("Chroma delete failed: %s", exc)

    def delete_repo(self, repo_id: str) -> None:
        """Drop an entire repository collection (used on repo deletion)."""
        try:
            client = self._connect()
            client.delete_collection(collection_name(repo_id))
            logger.info("Deleted vector collection for repo %s", repo_id)
        except Exception as exc:
            logger.debug("Nothing to delete for repo %s (%s)", repo_id, exc)

    def count(self, repo_id: str) -> int:
        try:
            return int(self.get_collection(repo_id, create=False).count())
        except Exception:
            return 0

    # ---------------------------------------------------------------- read
    def query(
        self,
        repo_id: str,
        *,
        query_embedding: Sequence[float],
        n_results: int = 5,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Nearest-neighbour search.

        Returns a list of ``{id, document, metadata, distance, score}`` dicts
        ordered by descending similarity (``score`` is ``1 - cosine_distance``).
        """
        collection = self.get_collection(repo_id, create=False)
        total = collection.count()
        if total == 0:
            return []

        result = collection.query(
            query_embeddings=[list(map(float, query_embedding))],
            n_results=min(n_results, total),
            where=where or None,
            include=["documents", "metadatas", "distances"],
        )

        hits: list[dict[str, Any]] = []
        ids = (result.get("ids") or [[]])[0]
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]

        for idx, chunk_id in enumerate(ids):
            distance = float(distances[idx]) if idx < len(distances) else 1.0
            hits.append(
                {
                    "id": chunk_id,
                    "document": documents[idx] if idx < len(documents) else "",
                    "metadata": metadatas[idx] if idx < len(metadatas) else {},
                    "distance": distance,
                    # Chroma cosine distance is in [0, 2]; map to a 0..1 score.
                    "score": max(0.0, 1.0 - distance),
                }
            )
        return hits

    def heartbeat(self) -> bool:
        """True when the vector store answers."""
        try:
            self._connect().heartbeat()
            return True
        except Exception:
            return False


def _clean_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Chroma only accepts str/int/float/bool metadata values."""
    cleaned: dict[str, Any] = {}
    for key, value in metadata.items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            cleaned[key] = value
        else:
            cleaned[key] = str(value)
    return cleaned


@lru_cache(maxsize=1)
def get_vector_store() -> VectorStore:
    """Process-wide vector store singleton."""
    return VectorStore()


__all__ = [
    "VectorStore",
    "VectorStoreUnavailable",
    "collection_name",
    "get_vector_store",
]
