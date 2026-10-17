"""
Retrieval-Augmented Generation over a user's repository.

Flow for ``POST /api/ai/chat``:

1. Embed the question with ``nomic-embed-text``.
2. Pull the top-K nearest code chunks from ChromaDB.
3. Assemble a numbered context block (with file paths + line ranges).
4. Ask Llama 3.2 to answer **using only that context**, citing files and
   functions.
5. Return the answer plus citation metadata for the UI.
"""

from __future__ import annotations

import time
import uuid
from collections import OrderedDict
from threading import Lock

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.models import Repository
from app.schemas.ai import ChatMessage, ChatResponse, Citation
from app.services.ai.embeddings import EmbeddingService, get_embedding_service
from app.services.llm import OllamaClient, OllamaUnavailable, get_ollama
from app.services.vectorstore import VectorStore, VectorStoreUnavailable, get_vector_store

logger = get_logger("rag")

# --------------------------------------------------------------------------- #
# Prompts
# --------------------------------------------------------------------------- #
SYSTEM_PROMPT = """You are a senior software engineer acting as the AI explainer \
inside a developer's own repository on GitFolio.

Rules you must follow:
1. Answer the developer's question using ONLY the numbered code snippets provided below.
2. Cite the source of every claim as `path/to/file.ext:line` (or `file.ext:startLine-endLine`).
3. When you name a function, class or module, use its exact identifier from the snippets.
4. If the snippets do not contain the answer, say so plainly and describe what you \
*would* need to see. Never invent files, functions or behaviour.
5. Be concrete and technical. Prefer short paragraphs and bullet points over long prose.
6. Assume the reader wrote this code and wants a precise walkthrough, not a tutorial.
"""

USER_PROMPT_TEMPLATE = """Repository: {repo_name} (primary language: {language})

--- BEGIN CODE CONTEXT ---
{context}
--- END CODE CONTEXT ---

Question: {question}

Answer using only the numbered snippets above. Cite files and line numbers.
"""

SUMMARY_PROMPT_TEMPLATE = """Below are the most relevant code snippets for the search query "{query}".

--- BEGIN SNIPPETS ---
{context}
--- END SNIPPETS ---

In 2-3 sentences, explain what the most relevant snippet does and whether it \
actually answers the query. Cite the file path.
"""


# --------------------------------------------------------------------------- #
# Tiny in-process answer cache
# --------------------------------------------------------------------------- #
class _AnswerCache:
    """Bounded LRU cache so repeated questions do not re-run the LLM."""

    def __init__(self, maxsize: int = 128) -> None:
        self._data: OrderedDict[str, ChatResponse] = OrderedDict()
        self._lock = Lock()
        self._maxsize = maxsize

    def get(self, key: str) -> ChatResponse | None:
        with self._lock:
            value = self._data.get(key)
            if value is not None:
                self._data.move_to_end(key)
            return value

    def set(self, key: str, value: ChatResponse) -> None:
        with self._lock:
            self._data[key] = value
            self._data.move_to_end(key)
            while len(self._data) > self._maxsize:
                self._data.popitem(last=False)

    def invalidate(self, repo_id: str) -> None:
        with self._lock:
            for key in [k for k in self._data if k.startswith(f"{repo_id}:")]:
                self._data.pop(key, None)


_answer_cache = _AnswerCache()


# --------------------------------------------------------------------------- #
# Retrieval
# --------------------------------------------------------------------------- #
def retrieve(
    repo_id: uuid.UUID | str,
    question: str,
    *,
    top_k: int | None = None,
    file_filter: str | None = None,
    embedder: EmbeddingService | None = None,
    store: VectorStore | None = None,
) -> list[dict]:
    """Embed ``question`` and return the nearest chunks (may be empty)."""
    embedder = embedder or get_embedding_service()
    store = store or get_vector_store()

    where = {"file_path": {"$contains": file_filter}} if file_filter else None
    vector = embedder.embed_query(question)

    hits = store.query(
        str(repo_id),
        query_embedding=vector,
        n_results=top_k or settings.RAG_TOP_K,
        where=where,
    )
    logger.debug("Retrieved %d chunks for %r", len(hits), question[:60])
    return hits


def build_context(hits: list[dict], max_chars: int | None = None) -> str:
    """Render retrieved chunks into a numbered, size-budgeted context block."""
    max_chars = max_chars or settings.RAG_MAX_CONTEXT_CHARS
    blocks: list[str] = []
    used = 0

    for index, hit in enumerate(hits, start=1):
        meta = hit.get("metadata") or {}
        source = hit.get("document") or ""
        header = (
            f"[{index}] {meta.get('file_path', 'unknown')} "
            f"(lines {meta.get('start_line', '?')}-{meta.get('end_line', '?')}"
        )
        if meta.get("symbol"):
            header += f", {meta.get('kind', 'block')} `{meta['symbol']}`"
        header += ")"

        body = source
        remaining = max_chars - used - len(header) - 8
        if remaining <= 0:
            break
        if len(body) > remaining:
            body = body[:remaining] + "\n... [truncated]"

        block = f"{header}\n{body}\n"
        blocks.append(block)
        used += len(block)

    return "\n".join(blocks)


def hits_to_citations(hits: list[dict], *, snippet_chars: int = 400) -> list[Citation]:
    """Convert raw vector hits into API citations."""
    citations: list[Citation] = []
    for hit in hits:
        meta = hit.get("metadata") or {}
        document = hit.get("document") or ""
        citations.append(
            Citation(
                file_path=str(meta.get("file_path", "unknown")),
                start_line=int(meta.get("start_line", 0) or 0),
                end_line=int(meta.get("end_line", 0) or 0),
                language=str(meta.get("language") or "") or None,
                symbol=str(meta.get("symbol") or "") or None,
                score=round(float(hit.get("score", 0.0)), 4),
                snippet=document[:snippet_chars],
            )
        )
    return citations


# --------------------------------------------------------------------------- #
# Chat
# --------------------------------------------------------------------------- #
def answer_question(
    db: Session,
    repo: Repository,
    question: str,
    *,
    top_k: int | None = None,
    history: list[ChatMessage] | None = None,
    file_filter: str | None = None,
    embedder: EmbeddingService | None = None,
    store: VectorStore | None = None,
    llm: OllamaClient | None = None,
) -> ChatResponse:
    """
    Run the full RAG pipeline for one question.

    Raises ``VectorStoreUnavailable`` / ``OllamaUnavailable`` which the route
    layer converts into 503 responses with actionable messages.
    """
    started = time.perf_counter()
    llm = llm or get_ollama()

    cache_key = f"{repo.id}:{top_k or settings.RAG_TOP_K}:{file_filter or ''}:{question.strip().lower()}"
    cached = _answer_cache.get(cache_key)
    if cached is not None:
        return cached.model_copy(update={"cached": True})

    hits = retrieve(
        repo.id,
        question,
        top_k=top_k,
        file_filter=file_filter,
        embedder=embedder,
        store=store,
    )

    if not hits:
        answer = (
            "I could not find any indexed code in this repository that matches your "
            "question. Push some files (or re-run indexing from the repo settings) "
            "and try again."
        )
        response = ChatResponse(
            answer=answer,
            citations=[],
            model=llm.chat_model,
            elapsed_ms=int((time.perf_counter() - started) * 1000),
        )
        return response

    context = build_context(hits)
    user_prompt = USER_PROMPT_TEMPLATE.format(
        repo_name=repo.name,
        language=repo.primary_language or "unknown",
        context=context,
        question=question.strip(),
    )

    messages: list[dict[str, str]] = []
    # Include a trimmed conversation history for follow-up questions.
    for turn in (history or [])[-6:]:
        messages.append({"role": turn.role, "content": turn.content})
    messages.append({"role": "user", "content": user_prompt})

    answer = llm.chat(
        messages,
        system=SYSTEM_PROMPT,
        temperature=0.15,
        max_tokens=1200,
    )

    response = ChatResponse(
        answer=answer,
        citations=hits_to_citations(hits),
        model=llm.chat_model,
        elapsed_ms=int((time.perf_counter() - started) * 1000),
    )
    _answer_cache.set(cache_key, response)
    return response


def summarise_hits(
    repo: Repository,
    query: str,
    hits: list[dict],
    *,
    llm: OllamaClient | None = None,
) -> str | None:
    """
    Ask Llama 3.2 for a one-paragraph summary of the search results.

    Returns ``None`` when the LLM is unreachable — search still works.
    """
    if not hits:
        return None
    llm = llm or get_ollama()
    context = build_context(hits, max_chars=6000)
    prompt = SUMMARY_PROMPT_TEMPLATE.format(query=query, context=context)
    try:
        return llm.chat(
            [{"role": "user", "content": prompt}],
            system="You are a precise code search assistant. Answer in at most 3 sentences.",
            temperature=0.1,
            max_tokens=220,
        )
    except (OllamaUnavailable, Exception) as exc:  # noqa: B014 - degrade gracefully
        logger.warning("Search summary unavailable: %s", exc)
        return None


def invalidate_repo_cache(repo_id: uuid.UUID | str) -> None:
    """Drop cached answers for a repo (called after a push changes its code)."""
    _answer_cache.invalidate(str(repo_id))


__all__ = [
    "SYSTEM_PROMPT",
    "answer_question",
    "build_context",
    "hits_to_citations",
    "invalidate_repo_cache",
    "retrieve",
    "summarise_hits",
]
