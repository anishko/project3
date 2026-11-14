"""Retrieval-augmented answering.

Returns the same contract Story #4 expects (see README_UserStories_4_13.md):
    {"answer": str, "sources": [{"title", "url", "source_name", "published_date", "excerpt", "disaster"}]}
"""
from __future__ import annotations

from django.conf import settings

from knowledge import retrieval
from knowledge.embeddings import EmbeddingError

from . import llm

NO_MATCH_ANSWER = (
    "I couldn't find anything about that in ReliefRoute's current sources, so I don't want to guess. "
    "Please check official guidance from your local emergency management office, FEMA (ready.gov), "
    "or the National Weather Service."
)


class RAGError(RuntimeError):
    """Base class; ``user_message`` is safe to show in the UI."""

    status = 500
    user_message = "Something went wrong while answering. Please try again."


class EmptyDatasetError(RAGError):
    status = 503
    user_message = "The knowledge base is empty. An admin needs to add documents and run ingestion."


class UpstreamError(RAGError):
    status = 502
    user_message = "The AI service is unavailable right now. Please try again in a minute."


def answer_question(question: str) -> dict:
    if not retrieval.active_chunks().exists():
        raise EmptyDatasetError("No active chunks for the current embedding model.")

    try:
        hits = retrieval.retrieve(question, top_k=settings.RAG_TOP_K, min_score=settings.RAG_MIN_SCORE)
    except EmbeddingError as exc:
        raise UpstreamError(str(exc)) from exc

    if not hits:
        return {"answer": NO_MATCH_ANSWER, "sources": []}

    contexts = [{"title": h.chunk.document.title, "text": h.chunk.text} for h in hits]
    try:
        answer = llm.generate_answer(question, contexts)
    except llm.LLMError as exc:
        raise UpstreamError(str(exc)) from exc

    sources, seen = [], set()
    for hit in hits:
        doc = hit.chunk.document
        if doc.pk in seen:
            continue
        seen.add(doc.pk)
        excerpt = hit.chunk.text[:220].rsplit(" ", 1)[0] + "…" if len(hit.chunk.text) > 220 else hit.chunk.text
        sources.append(
            {
                "title": doc.title,
                "url": doc.source_url,
                "source_name": doc.source_name,
                "published_date": doc.published_date,
                "excerpt": excerpt,
                "disaster": doc.disaster or doc.get_category_display(),
                "score": round(hit.score, 3),
            }
        )
    return {"answer": answer, "sources": sources}
