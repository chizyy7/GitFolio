"""
RAG ingestion pipeline.

File contents (from PostgreSQL) -> tree-sitter chunks -> Ollama embeddings
-> ChromaDB vectors + metadata.

The metadata stored alongside every vector is what makes citations possible:

    {
      "repo_id": "...", "file_path": "app/services/auth.py",
      "start_line": 42, "end_line": 88, "language": "Python",
      "symbol": "authenticate", "kind": "function"
    }
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models import File, Repository
from app.schemas.ai import IndexStatus
from app.services.ai.chunker import CodeChunk, chunk_file
from app.services.ai.embeddings import EmbeddingService, get_embedding_service
from app.services.language import is_indexable
from app.services.vectorstore import VectorStore, collection_name, get_vector_store

logger = get_logger("ingestion")


@dataclass(slots=True)
class PreparedChunk:
    """A chunk ready to be embedded, with its deterministic vector id."""

    chunk: CodeChunk
    vector_id: str

    @property
    def document(self) -> str:
        return self.chunk.text_for_embedding

    @property
    def metadata(self) -> dict[str, str | int]:
        return {
            "repo_id": str(self.chunk.metadata.get("repo_id", "")),
            "file_path": self.chunk.file_path,
            "start_line": self.chunk.start_line,
            "end_line": self.chunk.end_line,
            "language": self.chunk.language,
            "symbol": self.chunk.symbol or "",
            "kind": self.chunk.kind,
        }


def _vector_id(repo_id: uuid.UUID | str, chunk: CodeChunk) -> str:
    """Stable id so re-indexing updates instead of duplicating chunks."""
    return f"{repo_id}:{chunk.file_path}:{chunk.start_line}:{chunk.end_line}"


def prepare_chunks(repo_id: uuid.UUID | str, files: list[File]) -> tuple[list[PreparedChunk], int]:
    """
    Turn database file rows into embeddable chunks.

    Returns ``(prepared_chunks, skipped_file_count)``.
    """
    prepared: list[PreparedChunk] = []
    skipped = 0

    for file_row in files:
        if file_row.is_binary or not file_row.content.strip():
            skipped += 1
            continue
        if not is_indexable(file_row.file_path, file_row.size_bytes):
            skipped += 1
            continue

        chunks = chunk_file(file_row.file_path, file_row.content)
        if not chunks:
            skipped += 1
            continue

        for chunk in chunks:
            chunk.metadata["repo_id"] = str(repo_id)
            prepared.append(PreparedChunk(chunk=chunk, vector_id=_vector_id(repo_id, chunk)))

    return prepared, skipped


def index_repository(
    db: Session,
    repo: Repository,
    *,
    force: bool = True,
    embedder: EmbeddingService | None = None,
    store: VectorStore | None = None,
) -> IndexStatus:
    """
    (Re)index a repository into the vector store.

    ``force=True`` wipes the collection first, which is the only way to drop
    chunks belonging to deleted or renamed files.
    """
    started = time.perf_counter()
    embedder = embedder or get_embedding_service()
    store = store or get_vector_store()

    files = list(
        db.execute(select(File).where(File.repo_id == repo.id, File.is_binary == 0)).scalars()
    )

    if force:
        store.delete_repo(str(repo.id))

    prepared, skipped = prepare_chunks(repo.id, files)

    if not prepared:
        logger.info("Repo %s has nothing to index (%d files skipped)", repo.id, skipped)
        repo.indexed_at = _utcnow()
        db.commit()
        return IndexStatus(
            repo_id=repo.id,
            indexed_files=0,
            indexed_chunks=0,
            skipped_files=skipped,
            collection=collection_name(str(repo.id)),
            elapsed_ms=int((time.perf_counter() - started) * 1000),
        )

    documents = [item.document for item in prepared]
    metadatas = [item.metadata for item in prepared]
    ids = [item.vector_id for item in prepared]

    logger.info("Embedding %d chunks from %d files for repo %s", len(prepared), len(files), repo.name)
    vectors = embedder.embed_documents(documents, progress_every=4)

    written = store.upsert(
        str(repo.id), ids=ids, documents=documents, metadatas=metadatas, embeddings=vectors
    )

    repo.indexed_at = _utcnow()
    db.commit()

    elapsed = int((time.perf_counter() - started) * 1000)
    logger.info("Indexed %d chunks (%dms) for repo %s", written, elapsed, repo.name)

    return IndexStatus(
        repo_id=repo.id,
        indexed_files=len({p.chunk.file_path for p in prepared}),
        indexed_chunks=written,
        skipped_files=skipped,
        collection=collection_name(str(repo.id)),
        elapsed_ms=elapsed,
    )


def index_paths(
    db: Session,
    repo: Repository,
    paths: list[str],
    *,
    embedder: EmbeddingService | None = None,
    store: VectorStore | None = None,
) -> int:
    """
    Incrementally re-index only the given paths (used after a push).

    Stale chunks for those paths are removed before the new ones are added.
    """
    if not paths:
        return 0

    embedder = embedder or get_embedding_service()
    store = store or get_vector_store()

    files = list(
        db.execute(
            select(File).where(File.repo_id == repo.id, File.file_path.in_(paths), File.is_binary == 0)
        ).scalars()
    )
    prepared, _ = prepare_chunks(repo.id, files)

    prepared_paths = {item.chunk.file_path for item in prepared}
    for path in paths:
        # Remove everything previously stored for this path (covers deletions
        # and shrinking files) — including paths with no new chunks at all.
        store.delete_where(str(repo.id), {"file_path": path})

    if not prepared:
        return 0

    vectors = embedder.embed_documents([item.document for item in prepared])
    return store.upsert(
        str(repo.id),
        ids=[item.vector_id for item in prepared],
        documents=[item.document for item in prepared],
        metadatas=[item.metadata for item in prepared],
        embeddings=vectors,
    )


def remove_repository_index(repo_id: uuid.UUID | str) -> None:
    """Drop a repository's vectors (called on repo deletion)."""
    try:
        get_vector_store().delete_repo(str(repo_id))
    except Exception as exc:  # pragma: no cover - best effort
        logger.warning("Could not delete vectors for repo %s: %s", repo_id, exc)


def _utcnow():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)


__all__ = [
    "PreparedChunk",
    "index_paths",
    "index_repository",
    "prepare_chunks",
    "remove_repository_index",
]
