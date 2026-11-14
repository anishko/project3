from django.apps import AppConfig


class KnowledgeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "knowledge"
    verbose_name = "Knowledge base (RAG dataset)"

    def ready(self):
        from . import signals  # noqa: F401  (registers post_save / post_delete hooks)
