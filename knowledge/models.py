from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models

CATEGORY_CHOICES = [
    ("hurricane", "Hurricane"),
    ("flood", "Flood"),
    ("wildfire", "Wildfire"),
    ("general", "General preparedness / recovery"),
]


class Document(models.Model):
    """One curated source in the RAG dataset (an article, guide, PDF, ...)."""

    title = models.CharField(max_length=255)
    source_url = models.URLField(max_length=500, blank=True)
    source_name = models.CharField(max_length=120, blank=True, help_text="Publisher, e.g. FEMA, Associated Press.")
    category = models.CharField(max_length=40, choices=CATEGORY_CHOICES, default="general", db_index=True)
    disaster = models.CharField(max_length=120, blank=True, help_text="Specific event, e.g. Hurricane Helene (optional).")
    published_date = models.CharField(max_length=20, blank=True, help_text="Free-form, e.g. 2024-10-15 or 2025.")
    content = models.TextField(blank=True, help_text="Paste the text here, or upload a .txt/.pdf file instead.")
    file = models.FileField(
        upload_to="documents/",
        blank=True,
        validators=[FileExtensionValidator(["txt", "md", "pdf"])],
        help_text="Optional .txt, .md or .pdf. Used when the text field is empty.",
    )
    is_active = models.BooleanField(default=True, help_text="Inactive documents are ignored by the chatbot.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Ingestion bookkeeping (not edited by hand).
    content_hash = models.CharField(max_length=64, blank=True, editable=False)
    last_ingested_at = models.DateTimeField(null=True, blank=True, editable=False)
    ingest_error = models.TextField(blank=True, editable=False)
    seed_file = models.CharField(
        max_length=255, blank=True, db_index=True, editable=False,
        help_text="Set when the document was loaded from the data/ folder by ingest_documents.",
    )

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title

    def clean(self):
        if not self.content.strip() and not self.file:
            raise ValidationError("Provide either text content or an uploaded .txt/.pdf file.")


class Chunk(models.Model):
    """A slice of a document plus its embedding vector (stored as a JSON list)."""

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="chunks")
    chunk_index = models.PositiveIntegerField()
    text = models.TextField()
    embedding = models.JSONField()
    embedding_model = models.CharField(max_length=100, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["document_id", "chunk_index"]
        constraints = [models.UniqueConstraint(fields=["document", "chunk_index"], name="unique_chunk_per_document")]

    def __str__(self):
        return f"{self.document.title} #{self.chunk_index}"
