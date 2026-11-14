"""python manage.py ingest_documents [--rebuild] [--skip-seed] [--data-dir PATH]

1. Syncs seed files from data/ into Document rows (matched by file name).
2. Chunks + embeds every document whose text changed (or all of them with --rebuild).
"""
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models.signals import post_save

from knowledge.ingestion import ingest_document
from knowledge.models import CATEGORY_CHOICES, Document
from knowledge.signals import reingest_on_save

SEED_EXTENSIONS = {".txt", ".md", ".pdf"}
FRONT_MATTER_FIELDS = {"title", "source_url", "source_name", "category", "disaster", "published_date", "is_active"}
VALID_CATEGORIES = {key for key, _ in CATEGORY_CHOICES}


def parse_seed_text(raw: str) -> tuple[dict, str]:
    """Split optional 'key: value' front matter (ended by a line '---') from the body."""
    meta, lines = {}, raw.splitlines()
    if "---" in (line.strip() for line in lines[:15]):
        end = [line.strip() for line in lines].index("---")
        header = lines[:end]
        if all(":" in line for line in header if line.strip()):
            for line in header:
                if line.strip():
                    key, value = line.split(":", 1)
                    if key.strip().lower() in FRONT_MATTER_FIELDS:
                        meta[key.strip().lower()] = value.strip()
            return meta, "\n".join(lines[end + 1 :]).strip()
    return meta, raw.strip()


class Command(BaseCommand):
    help = "Load seed documents from data/ and (re)build chunk embeddings for the RAG dataset."

    def add_arguments(self, parser):
        parser.add_argument("--rebuild", action="store_true", help="Re-embed every document, even unchanged ones.")
        parser.add_argument("--skip-seed", action="store_true", help="Don't sync files from the data/ folder.")
        parser.add_argument("--data-dir", default=str(settings.SEED_DATA_DIR), help="Folder of seed .txt/.md/.pdf files.")

    def handle(self, *args, **opts):
        # Saving below would trigger the post_save ingestion hook; we ingest explicitly instead.
        post_save.disconnect(reingest_on_save, sender=Document)
        try:
            if not opts["skip_seed"]:
                self.sync_seed_folder(Path(opts["data_dir"]))
            self.ingest_all(force=opts["rebuild"])
        finally:
            post_save.connect(reingest_on_save, sender=Document)

    def sync_seed_folder(self, folder: Path):
        if not folder.is_dir():
            self.stdout.write(self.style.WARNING(f"Seed folder {folder} not found; skipping."))
            return
        for path in sorted(p for p in folder.iterdir() if p.suffix.lower() in SEED_EXTENSIONS):
            if path.suffix.lower() == ".pdf":
                from pypdf import PdfReader

                meta, body = {}, "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
            else:
                meta, body = parse_seed_text(path.read_text(encoding="utf-8"))
            category = meta.get("category", "general").lower()
            defaults = {
                "title": meta.get("title") or path.stem.replace("_", " ").replace("-", " ").title(),
                "source_url": meta.get("source_url", ""),
                "source_name": meta.get("source_name", ""),
                "category": category if category in VALID_CATEGORIES else "general",
                "disaster": meta.get("disaster", ""),
                "published_date": meta.get("published_date", ""),
                "content": body,
            }
            # Seed docs are keyed by file name, so editing the title in the file updates
            # the same row instead of creating a duplicate.
            doc = Document.objects.filter(seed_file=path.name).first()
            if doc is None:
                Document.objects.create(seed_file=path.name, **defaults)
                self.stdout.write(f"  + added   {path.name}")
            elif any(getattr(doc, k) != v for k, v in defaults.items()):
                for k, v in defaults.items():
                    setattr(doc, k, v)
                doc.save()
                self.stdout.write(f"  ~ updated {path.name}")

    def ingest_all(self, force: bool):
        counts = {"ingested": 0, "skipped": 0, "empty": 0, "error": 0}
        for doc in Document.objects.all():
            result = ingest_document(doc, force=force)
            counts[result.status] += 1
            if result.status == "error":
                self.stdout.write(self.style.ERROR(f"  ! {doc.title}: {result.error}"))
            elif result.status == "ingested":
                self.stdout.write(f"  ✓ {doc.title} ({result.chunks} chunks)")
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. ingested={counts['ingested']} unchanged={counts['skipped']} "
                f"empty={counts['empty']} errors={counts['error']}"
            )
        )
        if counts["error"]:
            raise SystemExit(1)
