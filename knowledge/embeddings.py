"""Embedding backends.

* ``openai``  – calls the OpenAI embeddings API (default model text-embedding-3-small).
* ``hashing`` – a tiny, offline bag-of-words hashing embedder. No network, no key.
  Used by the tests and handy for local development without an API key.
  Retrieval quality is much lower than the OpenAI backend.

Pick one with the EMBEDDING_BACKEND setting / env var.
"""
from __future__ import annotations

import hashlib
import re

import numpy as np
from django.conf import settings

HASHING_DIM = 512
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    "a an and are as at be by can do does for from has have how i if in is it its me my of on or our should "
    "that the their them there these they this to was we what when where which who why will with you your".split()
)


class EmbeddingError(RuntimeError):
    """Raised when embeddings cannot be produced (missing key, API failure, ...)."""


def backend_name() -> str:
    return getattr(settings, "EMBEDDING_BACKEND", "openai").lower()


def model_id() -> str:
    """Identifier stored on each Chunk so vectors from different models are never mixed."""
    if backend_name() == "hashing":
        return f"hashing-{HASHING_DIM}"
    return f"openai:{settings.OPENAI_EMBEDDING_MODEL}"


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    if backend_name() == "hashing":
        return [_hash_embed(t) for t in texts]
    return _openai_embed(texts)


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]


def _hash_embed(text: str) -> list[float]:
    vec = np.zeros(HASHING_DIM, dtype=np.float32)
    for token in _TOKEN_RE.findall(text.lower()):
        if token in _STOPWORDS or len(token) < 2:
            continue
        digest = hashlib.md5(token.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "little") % HASHING_DIM
        vec[idx] += 1.0 if digest[4] & 1 else -1.0
    norm = np.linalg.norm(vec)
    if norm:
        vec /= norm
    return vec.round(6).tolist()


def _openai_embed(texts: list[str], batch_size: int = 64) -> list[list[float]]:
    if not settings.OPENAI_API_KEY:
        raise EmbeddingError("OPENAI_API_KEY is not set. Add it to your .env file (or use EMBEDDING_BACKEND=hashing).")
    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=30, max_retries=2)
        vectors: list[list[float]] = []
        for start in range(0, len(texts), batch_size):
            batch = [t.replace("\n", " ") for t in texts[start : start + batch_size]]
            resp = client.embeddings.create(model=settings.OPENAI_EMBEDDING_MODEL, input=batch)
            vectors.extend(item.embedding for item in sorted(resp.data, key=lambda d: d.index))
        return vectors
    except EmbeddingError:
        raise
    except Exception as exc:  # network / auth / rate-limit errors from the SDK
        raise EmbeddingError(f"Embedding request failed: {exc}") from exc
