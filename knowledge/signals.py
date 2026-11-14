from django.db.models.signals import post_save
from django.dispatch import receiver

from .ingestion import ingest_document
from .models import Document


@receiver(post_save, sender=Document)
def reingest_on_save(sender, instance, raw=False, **kwargs):
    """Re-chunk and re-embed whenever a document is created or edited.

    Unchanged text is detected by hash and skipped, so toggling ``is_active``
    or fixing a typo in the title does not cost an embedding call.
    Deleting a document removes its chunks via the FK cascade.
    """
    if raw:  # loading fixtures
        return
    ingest_document(instance)
