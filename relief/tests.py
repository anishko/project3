from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from .services import normalize_rag_response

class Story4CitationTests(SimpleTestCase):
    def test_valid_sources_are_renderable_and_duplicates_removed(self):
        payload={"answer":"Grounded answer","sources":[{"title":"Source A","url":"https://example.com/a"},{"title":"Source A duplicate","url":"https://example.com/a"},{"title":"","url":"https://example.com/b"}]}
        result=normalize_rag_response(payload)
        self.assertEqual(result["answer"],"Grounded answer")
        self.assertEqual(len(result["citations"]),1)
    def test_missing_source_metadata_is_not_fabricated(self):
        self.assertEqual(normalize_rag_response({"answer":"Answer","sources":[{}]})["citations"],[])

    def test_source_without_url_is_kept_when_titled(self):
        result=normalize_rag_response({"answer":"A","sources":[{"title":"Pasted guide","url":""},{"title":"Pasted guide","url":""}]})
        self.assertEqual([c.title for c in result["citations"]],["Pasted guide"])

# The Story #4 chat page is now the interactive page in the `chat` app (see chat/tests.py),
# which reuses normalize_rag_response() and the same source-card styles.

class Story13ResourceFinderTests(TestCase):
    def test_matching_resource_results_render(self):
        r=self.client.get(reverse("relief:resource_finder"),{"location":"Asheville, NC","need":"housing","constraints":["accessible"]})
        self.assertEqual(r.status_code,200); self.assertContains(r,"Prioritized results"); self.assertContains(r,"Source date")
    def test_no_results_message(self):
        r=self.client.get(reverse("relief:resource_finder"),{"location":"Seattle, WA","need":"housing"})
        self.assertContains(r,"No matching verified resources")
