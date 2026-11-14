"""Turn Documents into embedded Chunks."""
from __future__ import annotations

import hashlib
import io
import logging
import re
from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from . import embeddings
from .models import Chunk, Document

logger = logging.getLogger(__name__)

# We approximate tokens from words (~1.33 tokens per English word) instead of using
# tiktoken, which downloads its encoding files at runtime from a host that is not on
# PythonAnywhere's free-tier allowlist.
TOKENS_PER_WORD = 4 / 3
DEFAULT_CHUNK_TOKENS = 500
DEFAULT_OVERLAP_TOKENS = 50


def chunk_text(text: str, chunk_tokens: int = DEFAULT_CHUNK_TOKENS, overlap_tokens: int = DEFAULT_OVERLAP_TOKENS) -> list[str]:
    """Split text into ~chunk_tokens-sized windows that overlap by ~overlap_tokens."""
    words = text.split()
    if not words:
        return []
    size = max(1, int(chunk_tokens / TOKENS_PER_WORD))
    overlap = max(0, min(int(overlap_tokens / TOKENS_PER_WORD), size - 1))
    step = size - overlap
    chunks = []
    for start in range(0, len(words), step):
        chunks.append(" ".join(words[start : start + size]))
        if start + size >= len(words):
            break
    return chunks


def extract_text(document: Document) -> str:
    """Return the document's text: the content field, else the uploaded file."""
    if document.content.strip():
        return document.content
    if not document.file:
        return ""
    name = document.file.name.lower()
    document.file.open("rb")
    try:
        raw = document.file.read()
    finally:
        document.file.close()
    if name.endswith(".pdf"):
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(raw))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    return raw.decode("utf-8", errors="replace")


def _clean(text: str) -> str:
    text = text.replace("\x00", " ")
    return re.sub(r"[ \t]+", " ", text).strip()


@dataclass
class IngestResult:
    document: Document
    status: str  # "ingested", "skipped", "empty", "error"
    chunks: int = 0
    error: str = ""


def ingest_document(document: Document, force: bool = False) -> IngestResult:
    """(Re)build the chunks for one document.

    Skips the embedding call when the text and embedding model are unchanged,
    unless ``force`` is True. Old chunks are always replaced, never left stale.
    """
    model_id = embeddings.model_id()
    try:
        text = _clean(extract_text(document))
    except Exception as exc:
        return _record_error(document, f"Could not read file: {exc}")

    content_hash = hashlib.sha256(f"{model_id}\n{text}".encode("utf-8")).hexdigest()
    if not force and content_hash == document.content_hash and document.chunks.exists():
        return IngestResult(document, "skipped", document.chunks.count())

    pieces = chunk_text(text)
    try:
        vectors = embeddings.embed_texts(pieces)
    except embeddings.EmbeddingError as exc:
        return _record_error(document, str(exc))

    with transaction.atomic():
        document.chunks.all().delete()
        Chunk.objects.bulk_create(
            Chunk(document=document, chunk_index=i, text=piece, embedding=vec, embedding_model=model_id)
            for i, (piece, vec) in enumerate(zip(pieces, vectors))
        )
        # .update() avoids firing post_save again (which would re-trigger ingestion).
        now = timezone.now()
        Document.objects.filter(pk=document.pk).update(content_hash=content_hash, last_ingested_at=now, ingest_error="")
        document.content_hash, document.last_ingested_at, document.ingest_error = content_hash, now, ""

    return IngestResult(document, "ingested" if pieces else "empty", len(pieces))


def _record_error(document: Document, message: str) -> IngestResult:
    logger.warning("Ingestion failed for document %s (%s): %s", document.pk, document.title, message)
    Document.objects.filter(pk=document.pk).update(ingest_error=message[:2000])
    document.ingest_error = message
    return IngestResult(document, "error", error=message)
