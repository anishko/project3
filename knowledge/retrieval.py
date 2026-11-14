"""Cosine-similarity search over active chunks, in numpy (no vector DB needed)."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import embeddings
from .models import Chunk


@dataclass
class RetrievedChunk:
    chunk: Chunk
    score: float


def active_chunks():
    return Chunk.objects.filter(document__is_active=True, embedding_model=embeddings.model_id()).select_related("document")


def rank_chunks(query_vector, chunks, top_k: int = 4, min_score: float = 0.0) -> list[RetrievedChunk]:
    """Pure ranking step: score every chunk against the query and return the best."""
    chunks = list(chunks)
    if not chunks:
        return []
    matrix = np.asarray([c.embedding for c in chunks], dtype=np.float32)
    query = np.asarray(query_vector, dtype=np.float32)
    norms = np.linalg.norm(matrix, axis=1) * (np.linalg.norm(query) or 1.0)
    norms[norms == 0] = 1.0
    scores = matrix @ query / norms
    order = np.argsort(-scores)[:top_k]
    return [RetrievedChunk(chunks[i], float(scores[i])) for i in order if scores[i] >= min_score]


def retrieve(question: str, top_k: int = 4, min_score: float = 0.0) -> list[RetrievedChunk]:
    chunks = list(active_chunks())
    if not chunks:
        return []
    return rank_chunks(embeddings.embed_query(question), chunks, top_k=top_k, min_score=min_score)
