"""AI chat / semantic search schemas."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """A single turn in the conversation (sent by the client for context)."""

    role: str = Field(pattern="^(user|assistant|system)$")
    content: str = Field(max_length=8000)


class Citation(BaseModel):
    """A retrieved code chunk the answer is grounded in."""

    file_path: str
    start_line: int
    end_line: int
    language: str | None = None
    symbol: str | None = Field(default=None, description="Function/class name the chunk belongs to")
    score: float = Field(description="Similarity score (1.0 = identical)")
    snippet: str = Field(default="", description="Truncated source preview")


class ChatRequest(BaseModel):
    """``POST /api/ai/chat`` payload."""

    repo_id: uuid.UUID
    question: str = Field(min_length=1, max_length=4000)
    top_k: int | None = Field(default=None, ge=1, le=20)
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)
    file_filter: str | None = Field(default=None, max_length=512)


class ChatResponse(BaseModel):
    """Answer + the chunks it cites."""

    answer: str
    citations: list[Citation] = Field(default_factory=list)
    model: str
    elapsed_ms: int
    cached: bool = False


class SearchRequest(BaseModel):
    """``POST /api/ai/search`` payload."""

    repo_id: uuid.UUID
    query: str = Field(min_length=1, max_length=500)
    top_k: int = Field(default=8, ge=1, le=25)
    summarise: bool = Field(default=True, description="Ask Llama 3.2 for a short summary")


class SearchHit(BaseModel):
    """One semantic search result."""

    file_path: str
    start_line: int
    end_line: int
    language: str | None = None
    symbol: str | None = None
    score: float
    snippet: str
    summary: str | None = None


class SearchResponse(BaseModel):
    """Ranked semantic search results."""

    query: str
    results: list[SearchHit] = Field(default_factory=list)
    elapsed_ms: int


class IndexStatus(BaseModel):
    """Result of (re)indexing a repository into ChromaDB."""

    repo_id: uuid.UUID
    indexed_files: int
    indexed_chunks: int
    skipped_files: int = 0
    collection: str
    elapsed_ms: int


class ReviewResponse(BaseModel):
    """AI review for a commit (empty list while the background task runs)."""

    commit_id: uuid.UUID
    commit_hash: str
    status: str = Field(description="'pending' | 'complete' | 'failed' | 'disabled'")
    reviews: list["AIReviewReadLite"] = Field(default_factory=list)
    error: str | None = None


class AIReviewReadLite(BaseModel):
    """Trimmed review comment used by ``GET /api/ai/reviews/{commit_id}``."""

    id: uuid.UUID
    review_text: str
    line_number: int | None = None
    file_path: str | None = None
    severity: str
    title: str | None = None


ReviewResponse.model_rebuild()
