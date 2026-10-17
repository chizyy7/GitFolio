"""
AI services package.

* ``chunker``        – tree-sitter AST chunking
* ``embeddings``     – Ollama embedding wrapper
* ``ingestion``      – repo -> ChromaDB indexing pipeline
* ``rag``            – retrieval-augmented chat
* ``reviewer``       – Llama 3.2 code review of a commit diff
* ``commit_message`` – auto-generated commit messages
* ``skills``         – AI skill mapper
"""

from app.services.ai import chunker, commit_message, embeddings, ingestion, rag, reviewer, skills

__all__ = ["chunker", "commit_message", "embeddings", "ingestion", "rag", "reviewer", "skills"]
