"""
Ollama client — the only LLM provider GitFolio talks to.

Everything runs locally against ``llama3.2`` (chat) and ``nomic-embed-text``
(embeddings).  No paid API is ever contacted.

The client is deliberately synchronous: FastAPI runs it inside a thread pool
(``anyio.to_thread``) so a long generation never blocks the event loop.
"""

from __future__ import annotations

import json
import re
import time
from functools import lru_cache
from typing import Any, Iterable

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("ollama")


class OllamaUnavailable(RuntimeError):
    """Raised when the Ollama daemon cannot be reached."""


class OllamaResponseError(RuntimeError):
    """Raised when Ollama answers with an unusable payload."""


# --------------------------------------------------------------------------- #
# JSON coercion helpers (LLMs love markdown fences)
# --------------------------------------------------------------------------- #
_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def extract_json_payload(text: str) -> Any:
    """
    Best-effort extraction of a JSON value from raw LLM output.

    Handles: bare JSON, ```json fences, and prose surrounding an object/array.
    Raises ``ValueError`` when nothing parseable is found.
    """
    if not text:
        raise ValueError("Empty LLM response")

    candidate = text.strip()

    # 1. Straight parse.
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    # 2. Fenced code block.
    match = _FENCE_RE.search(candidate)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            candidate = match.group(1).strip()

    # 3. First balanced object/array.
    for opener, closer in (("{", "}"), ("[", "]")):
        start = candidate.find(opener)
        if start == -1:
            continue
        depth = 0
        in_string = False
        escaped = False
        for idx in range(start, len(candidate)):
            char = candidate[idx]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == opener:
                depth += 1
            elif char == closer:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(candidate[start : idx + 1])
                    except json.JSONDecodeError:
                        break

    raise ValueError(f"Could not extract JSON from LLM output: {text[:200]!r}")


# --------------------------------------------------------------------------- #
# Client
# --------------------------------------------------------------------------- #
class OllamaClient:
    """Minimal, typed wrapper around the Ollama HTTP API."""

    def __init__(
        self,
        host: str | None = None,
        chat_model: str | None = None,
        embed_model: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.host = (host or settings.OLLAMA_HOST).rstrip("/")
        self.chat_model = chat_model or settings.OLLAMA_CHAT_MODEL
        self.embed_model = embed_model or settings.OLLAMA_EMBED_MODEL
        self.timeout = timeout or settings.OLLAMA_TIMEOUT_SECONDS
        self._client = httpx.Client(base_url=self.host, timeout=self.timeout)

    # ----------------------------------------------------------- plumbing
    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "OllamaClient":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.8, min=0.8, max=8),
        retry=retry_if_exception_type((httpx.TransportError, OllamaResponseError)),
    )
    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self._client.post(path, json=payload)
        except httpx.TransportError as exc:
            raise OllamaUnavailable(
                f"Cannot reach Ollama at {self.host}: {exc}. "
                "Is `ollama serve` running and is the model pulled?"
            ) from exc

        if response.status_code == 404:
            raise OllamaResponseError(
                f"Ollama model not found. Run: ollama pull {payload.get('model')}"
            )
        if response.status_code >= 400:
            raise OllamaResponseError(f"Ollama HTTP {response.status_code}: {response.text[:400]}")

        try:
            return response.json()
        except ValueError as exc:
            raise OllamaResponseError("Ollama returned a non-JSON body") from exc

    # ------------------------------------------------------------ health
    def is_available(self) -> bool:
        """True when the daemon answers and the chat model is present."""
        try:
            response = self._client.get("/api/tags", timeout=5.0)
            response.raise_for_status()
            models = {m.get("name", "").split(":")[0] for m in response.json().get("models", [])}
            return self.chat_model.split(":")[0] in models
        except Exception:
            return False

    def list_models(self) -> list[str]:
        try:
            response = self._client.get("/api/tags", timeout=10.0)
            response.raise_for_status()
            return [m.get("name", "") for m in response.json().get("models", [])]
        except Exception as exc:
            logger.warning("Could not list Ollama models: %s", exc)
            return []

    def ensure_models(self) -> None:
        """Pull the required models if they are missing (idempotent)."""
        available = {name.split(":")[0] for name in self.list_models()}
        for model in (self.chat_model, self.embed_model):
            base = model.split(":")[0]
            if base in available:
                continue
            logger.info("Pulling Ollama model %s (this may take a while)…", model)
            try:
                with self._client.stream("POST", "/api/pull", json={"model": model}, timeout=None) as r:
                    for _ in r.iter_lines():
                        pass
            except Exception as exc:  # pragma: no cover - infra dependent
                logger.error("Failed to pull %s: %s", model, exc)

    # -------------------------------------------------------------- chat
    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 1024,
        json_mode: bool = False,
        system: str | None = None,
    ) -> str:
        """
        Run a chat completion and return the assistant message content.

        ``json_mode=True`` forces Ollama's constrained-JSON decoding, which
        dramatically improves reliability for the reviewer / skill mapper.
        """
        payload_messages: list[dict[str, str]] = []
        if system:
            payload_messages.append({"role": "system", "content": system})
        payload_messages.extend(messages)

        payload: dict[str, Any] = {
            "model": model or self.chat_model,
            "messages": payload_messages,
            "stream": False,
            "keep_alive": settings.OLLAMA_KEEP_ALIVE,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                "top_p": 0.9,
                "repeat_penalty": 1.05,
            },
        }
        if json_mode:
            payload["format"] = "json"

        data = self._post("/api/chat", payload)
        message = data.get("message") or {}
        content = message.get("content")
        if not isinstance(content, str):
            raise OllamaResponseError("Ollama chat response is missing `message.content`")
        return content.strip()

    def chat_json(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 1500,
        system: str | None = None,
    ) -> Any:
        """Chat with constrained JSON decoding and parse the result."""
        raw = self.chat(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=True,
            system=system,
        )
        return extract_json_payload(raw)

    def generate(
        self,
        prompt: str,
        *,
        model: str | None = None,
        system: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 512,
    ) -> str:
        """Raw completion (used by the auto-commit message generator)."""
        payload: dict[str, Any] = {
            "model": model or self.chat_model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": settings.OLLAMA_KEEP_ALIVE,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        if system:
            payload["system"] = system
        data = self._post("/api/generate", payload)
        response = data.get("response")
        if not isinstance(response, str):
            raise OllamaResponseError("Ollama generate response is missing `response`")
        return response.strip()

    # -------------------------------------------------------- embeddings
    def embed(self, texts: Iterable[str], *, model: str | None = None) -> list[list[float]]:
        """
        Embed a batch of texts.

        Uses ``/api/embed`` (Ollama >= 0.2) and transparently falls back to
        the legacy ``/api/embeddings`` endpoint for each text.
        """
        items = [t for t in texts]
        if not items:
            return []

        target = model or self.embed_model
        try:
            data = self._post("/api/embed", {"model": target, "input": items, "keep_alive": settings.OLLAMA_KEEP_ALIVE})
            embeddings = data.get("embeddings")
            if isinstance(embeddings, list) and len(embeddings) == len(items):
                return [[float(x) for x in vec] for vec in embeddings]
        except OllamaResponseError as exc:
            logger.debug("/api/embed unavailable (%s); falling back to /api/embeddings", exc)

        vectors: list[list[float]] = []
        for text in items:
            data = self._post(
                "/api/embeddings",
                {"model": target, "prompt": text, "keep_alive": settings.OLLAMA_KEEP_ALIVE},
            )
            vector = data.get("embedding")
            if not isinstance(vector, list):
                raise OllamaResponseError("Ollama embeddings response is missing `embedding`")
            vectors.append([float(x) for x in vector])
        return vectors

    def embed_one(self, text: str, *, model: str | None = None) -> list[float]:
        """Embed a single string (queries, mostly)."""
        vectors = self.embed([text], model=model)
        if not vectors:
            raise OllamaResponseError("Embedding model returned no vector")
        return vectors[0]


@lru_cache(maxsize=1)
def get_ollama() -> OllamaClient:
    """Process-wide Ollama client singleton."""
    return OllamaClient()


def timed(func):  # pragma: no cover - tiny convenience decorator
    """Log how long an LLM call took (handy while tuning prompts)."""

    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            logger.debug("%s took %.2fs", func.__name__, time.perf_counter() - start)

    return wrapper


__all__ = [
    "OllamaClient",
    "OllamaResponseError",
    "OllamaUnavailable",
    "extract_json_payload",
    "get_ollama",
    "timed",
]
