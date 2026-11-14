import json
from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse

from knowledge.models import Document

from . import llm


@override_settings(EMBEDDING_BACKEND="hashing", RAG_MIN_SCORE=0.0, OPENAI_API_KEY="test-key")
class ChatEndpointTests(TestCase):
    def post(self, body):
        return self.client.post(reverse("chat:ask"), data=json.dumps(body), content_type="application/json")

    def add_docs(self):
        Document.objects.create(
            title="Flash Flood Safety", source_url="https://www.weather.gov/safety/flood", source_name="NWS",
            category="flood", content="Never drive through flood water. Turn around, don't drown.",
        )
        Document.objects.create(title="Go-bag", category="general", content="Pack water, a flashlight and medications.")

    def test_chat_page_renders(self):
        r = self.client.get(reverse("chat:index"))
        self.assertContains(r, 'id="chat-form"')
        self.assertIn("csrftoken", r.cookies)

    @mock.patch("chat.llm.generate_answer", return_value="Do not drive through flood water [1].")
    def test_answer_includes_sources(self, mocked):
        self.add_docs()
        r = self.post({"question": "Can I drive through flood water?"})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["answer"], "Do not drive through flood water [1].")
        self.assertEqual(data["sources"][0]["title"], "Flash Flood Safety")
        self.assertEqual(data["sources"][0]["url"], "https://www.weather.gov/safety/flood")
        question, contexts = mocked.call_args.args
        self.assertEqual(question, "Can I drive through flood water?")
        self.assertIn("flood water", contexts[0]["text"])

    def test_prompt_restricts_model_to_context(self):
        messages = llm.build_messages("Q?", [{"title": "Doc", "text": "ctx"}])
        self.assertIn("ONLY", messages[0]["content"])
        self.assertIn("don't know", messages[0]["content"])
        self.assertIn("[1] Doc\nctx", messages[1]["content"])

    def test_empty_dataset_returns_friendly_error(self):
        r = self.post({"question": "Anything?"})
        self.assertEqual(r.status_code, 503)
        self.assertIn("knowledge base is empty", r.json()["error"])

    @mock.patch("chat.llm.generate_answer", side_effect=llm.LLMError("boom"))
    def test_llm_failure_returns_friendly_error(self, _):
        self.add_docs()
        r = self.post({"question": "flood water?"})
        self.assertEqual(r.status_code, 502)
        self.assertNotIn("boom", r.json()["error"])  # internal details are not leaked

    def test_blank_and_invalid_questions_are_rejected(self):
        self.assertEqual(self.post({"question": "   "}).status_code, 400)
        self.assertEqual(self.post({"question": "x" * 1001}).status_code, 400)
        bad = self.client.post(reverse("chat:ask"), data="not json", content_type="application/json")
        self.assertEqual(bad.status_code, 400)

    def test_get_not_allowed(self):
        self.assertEqual(self.client.get(reverse("chat:ask")).status_code, 405)

    @mock.patch("chat.llm.generate_answer")
    def test_no_relevant_chunks_skips_llm(self, mocked):
        self.add_docs()
        with self.settings(RAG_MIN_SCORE=0.99):
            r = self.post({"question": "volcano ash"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["sources"], [])
        mocked.assert_not_called()

    def test_csrf_is_enforced(self):
        client = self.client_class(enforce_csrf_checks=True)
        r = client.post(reverse("chat:ask"), data=json.dumps({"question": "hi"}), content_type="application/json")
        self.assertEqual(r.status_code, 403)
