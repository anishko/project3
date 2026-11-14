from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.files.base import ContentFile
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings

from .ingestion import TOKENS_PER_WORD, chunk_text, ingest_document
from .management.commands.ingest_documents import parse_seed_text
from .models import Chunk, Document
from .retrieval import rank_chunks, retrieve


class ChunkingTests(SimpleTestCase):
    def test_empty_text_has_no_chunks(self):
        self.assertEqual(chunk_text("   \n "), [])

    def test_short_text_is_one_chunk(self):
        self.assertEqual(chunk_text("pack water and a flashlight"), ["pack water and a flashlight"])

    def test_long_text_is_split_with_overlap(self):
        words = [f"w{i}" for i in range(1000)]
        chunks = chunk_text(" ".join(words), chunk_tokens=100, overlap_tokens=20)
        size, overlap = int(100 / TOKENS_PER_WORD), int(20 / TOKENS_PER_WORD)
        self.assertTrue(all(len(c.split()) <= size for c in chunks))
        first, second = chunks[0].split(), chunks[1].split()
        self.assertEqual(first[-overlap:], second[:overlap])  # overlap carried forward
        self.assertEqual(chunks[-1].split()[-1], "w999")  # nothing dropped at the end

    def test_seed_front_matter_is_parsed(self):
        meta, body = parse_seed_text("title: Flood Tips\ncategory: flood\n---\nMove to higher ground.")
        self.assertEqual(meta, {"title": "Flood Tips", "category": "flood"})
        self.assertEqual(body, "Move to higher ground.")


class FakeChunk:
    def __init__(self, name, embedding):
        self.name, self.embedding = name, embedding


class RankingTests(SimpleTestCase):
    def test_chunks_are_ranked_by_cosine_similarity(self):
        chunks = [FakeChunk("orthogonal", [0, 1, 0]), FakeChunk("best", [1, 0, 0]), FakeChunk("close", [1, 1, 0])]
        ranked = rank_chunks([2, 0, 0], chunks, top_k=3)
        self.assertEqual([r.chunk.name for r in ranked], ["best", "close", "orthogonal"])
        self.assertAlmostEqual(ranked[0].score, 1.0, places=5)

    def test_top_k_and_min_score(self):
        chunks = [FakeChunk("a", [1, 0]), FakeChunk("b", [0.9, 0.1]), FakeChunk("c", [0, 1])]
        self.assertEqual(len(rank_chunks([1, 0], chunks, top_k=1)), 1)
        self.assertEqual([r.chunk.name for r in rank_chunks([1, 0], chunks, top_k=5, min_score=0.5)], ["a", "b"])


@override_settings(EMBEDDING_BACKEND="hashing")
class IngestionTests(TestCase):
    def make_doc(self, **kw):
        defaults = {"title": "Flood safety", "content": "Never drive through flood water. Move to higher ground."}
        defaults.update(kw)
        return Document.objects.create(**defaults)

    def test_saving_a_document_creates_chunks(self):
        doc = self.make_doc()
        self.assertEqual(doc.chunks.count(), 1)
        self.assertEqual(doc.chunks.first().embedding_model, "hashing-512")

    def test_editing_text_replaces_stale_chunks(self):
        doc = self.make_doc()
        old_ids = set(doc.chunks.values_list("id", flat=True))
        doc.content = " ".join(["evacuate"] * 900)
        doc.save()
        new_ids = set(doc.chunks.values_list("id", flat=True))
        self.assertTrue(old_ids.isdisjoint(new_ids))
        self.assertGreater(len(new_ids), 1)

    def test_unchanged_text_is_skipped(self):
        doc = self.make_doc()
        self.assertEqual(ingest_document(doc).status, "skipped")
        self.assertEqual(ingest_document(doc, force=True).status, "ingested")

    def test_deleting_document_deletes_chunks(self):
        self.make_doc().delete()
        self.assertEqual(Chunk.objects.count(), 0)

    def test_uploaded_txt_file_is_ingested(self):
        with TemporaryDirectory() as media, self.settings(MEDIA_ROOT=media):
            doc = Document(title="Upload")
            doc.file.save("tips.txt", ContentFile(b"Charge your phone before the storm."), save=True)
            self.assertIn("Charge your phone", doc.chunks.first().text)

    def test_retrieval_ignores_inactive_documents(self):
        self.make_doc(title="Hurricane", content="hurricane evacuation zone routes shelter")
        self.make_doc(title="Flood", content="flood water higher ground", is_active=False)
        titles = [h.chunk.document.title for h in retrieve("flood water", top_k=5)]
        self.assertNotIn("Flood", titles)

    def test_retrieval_puts_relevant_document_first(self):
        self.make_doc(title="Go-bag", content="pack water flashlight batteries medications documents in a go-bag")
        self.make_doc(title="FEMA", content="apply for FEMA disaster assistance online inspection appeal")
        self.assertEqual(retrieve("how do I apply for FEMA assistance")[0].chunk.document.title, "FEMA")

    def test_management_command_loads_seed_folder(self):
        with TemporaryDirectory() as tmp:
            Path(tmp, "a.txt").write_text("title: Seed A\ncategory: flood\n---\nflood safety text", encoding="utf-8")
            out = StringIO()
            call_command("ingest_documents", data_dir=tmp, stdout=out)
            call_command("ingest_documents", data_dir=tmp, stdout=out)  # idempotent
            doc = Document.objects.get()
            self.assertEqual((doc.title, doc.category, doc.seed_file), ("Seed A", "flood", "a.txt"))
            self.assertEqual(doc.chunks.count(), 1)
            call_command("ingest_documents", data_dir=tmp, rebuild=True, stdout=out)
            self.assertIn("ingested=1", out.getvalue().splitlines()[-1])


@override_settings(EMBEDDING_BACKEND="hashing")
class AdminTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        self.client.force_login(get_user_model().objects.create_superuser("admin", "a@example.com", "pw"))

    def test_admin_pages_render_and_add_document(self):
        self.assertEqual(self.client.get("/admin/knowledge/document/").status_code, 200)
        self.assertEqual(self.client.get("/admin/knowledge/chunk/").status_code, 200)
        r = self.client.post("/admin/knowledge/document/add/", {
            "title": "Admin doc", "category": "flood", "is_active": "on", "content": "Move to higher ground.",
            "chunks-TOTAL_FORMS": "0", "chunks-INITIAL_FORMS": "0",
        })
        self.assertEqual(r.status_code, 302)
        doc = Document.objects.get(title="Admin doc")
        self.assertEqual(doc.chunks.count(), 1)
        self.assertEqual(self.client.get(f"/admin/knowledge/document/{doc.pk}/change/").status_code, 200)

    def test_admin_rejects_document_without_content_or_file(self):
        r = self.client.post("/admin/knowledge/document/add/", {
            "title": "Empty", "category": "flood", "content": "",
            "chunks-TOTAL_FORMS": "0", "chunks-INITIAL_FORMS": "0",
        })
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Document.objects.filter(title="Empty").exists())
