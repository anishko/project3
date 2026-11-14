from django.contrib import admin, messages

from .ingestion import ingest_document
from .models import Chunk, Document


class ChunkInline(admin.TabularInline):
    model = Chunk
    extra = 0
    can_delete = False
    fields = ("chunk_index", "text", "embedding_model")
    readonly_fields = fields
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "disaster", "is_active", "chunk_count", "ingest_status", "updated_at")
    list_filter = ("is_active", "category")
    list_editable = ("is_active",)
    search_fields = ("title", "content", "source_url", "disaster")
    readonly_fields = ("created_at", "updated_at", "last_ingested_at", "ingest_error")
    fieldsets = (
        (None, {"fields": ("title", "is_active", "category", "disaster")}),
        ("Source", {"fields": ("source_name", "source_url", "published_date")}),
        ("Content", {"fields": ("content", "file"), "description": "Paste text or upload a .txt/.md/.pdf file."}),
        ("Ingestion", {"fields": ("last_ingested_at", "ingest_error", "created_at", "updated_at"), "classes": ("collapse",)}),
    )
    inlines = [ChunkInline]
    actions = ["activate", "deactivate", "reingest"]

    @admin.display(description="Chunks")
    def chunk_count(self, obj):
        return obj.chunks.count()

    @admin.display(description="Ingestion", boolean=True)
    def ingest_status(self, obj):
        return bool(obj.last_ingested_at) and not obj.ingest_error

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)  # post_save signal ingests
        if obj.ingest_error:
            self.message_user(request, f"Saved, but ingestion failed: {obj.ingest_error}", messages.ERROR)

    @admin.action(description="Activate selected documents")
    def activate(self, request, queryset):
        queryset.update(is_active=True)

    @admin.action(description="Deactivate selected documents (hide from chatbot)")
    def deactivate(self, request, queryset):
        queryset.update(is_active=False)

    @admin.action(description="Re-embed selected documents now")
    def reingest(self, request, queryset):
        results = [ingest_document(doc, force=True) for doc in queryset]
        failed = [r for r in results if r.status == "error"]
        self.message_user(request, f"Re-ingested {len(results) - len(failed)} document(s).")
        for r in failed:
            self.message_user(request, f"{r.document.title}: {r.error}", messages.ERROR)


@admin.register(Chunk)
class ChunkAdmin(admin.ModelAdmin):
    list_display = ("document", "chunk_index", "embedding_model", "created_at")
    list_filter = ("embedding_model", "document__is_active")
    search_fields = ("text", "document__title")
    readonly_fields = ("document", "chunk_index", "text", "embedding_model", "created_at")
    exclude = ("embedding",)

    def has_add_permission(self, request):
        return False
