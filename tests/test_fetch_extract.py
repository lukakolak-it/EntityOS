from __future__ import annotations

import unittest

from target_radar.domain import Evidence, Target, TargetPage, TargetStatus
from target_radar.pipeline import (
    FakeFetcher,
    FetchedPage,
    HtmlExtractor,
    classify_page_type,
)
from target_radar.storage import SQLiteStore


HTML_FIXTURE = """
<!doctype html>
<html>
  <head>
    <title>Karriere bei Example</title>
    <meta name="description" content="Jobs und Werkstudentenstellen">
    <style>.hidden { display: none; }</style>
  </head>
  <body>
    <nav>Navigation</nav>
    <main>
      <h1>Werkstudent IT gesucht</h1>
      <p>Wir suchen Unterstuetzung in Softwareentwicklung und Python.</p>
      <p>Kontakt: jobs@example.com</p>
      <a href="/kontakt">Kontakt</a>
    </main>
    <script>ignored()</script>
  </body>
</html>
"""


class FetchExtractTests(unittest.TestCase):
    def test_fake_fetcher_returns_fixture_or_error(self) -> None:
        fetcher = FakeFetcher(
            pages={
                "https://example.com/jobs": FetchedPage(
                    url="https://example.com/jobs",
                    status_code=200,
                    body=HTML_FIXTURE,
                    content_type="text/html",
                )
            }
        )

        self.assertTrue(fetcher.fetch("https://example.com/jobs").ok)
        self.assertFalse(fetcher.fetch("https://example.com/missing").ok)

    def test_html_extractor_returns_text_links_emails_and_page_type(self) -> None:
        extracted = HtmlExtractor().extract("https://example.com/jobs", HTML_FIXTURE)

        self.assertEqual(extracted.page_type, "career")
        self.assertEqual(extracted.title, "Karriere bei Example")
        self.assertIn("Werkstudent IT gesucht", extracted.text)
        self.assertIn("jobs@example.com", extracted.emails)
        self.assertIn("https://example.com/kontakt", extracted.links)
        self.assertNotIn("ignored", extracted.text)

    def test_page_type_classifier_handles_contact_pages(self) -> None:
        self.assertEqual(
            classify_page_type("https://example.com/impressum"),
            "contact",
        )

    def test_target_pages_and_evidence_are_persisted(self) -> None:
        store = SQLiteStore.open(":memory:")
        try:
            target = store.create_target(
                Target(
                    domain="example.com",
                    base_url="https://example.com",
                    status=TargetStatus.FETCH_PENDING,
                )
            )
            extracted = HtmlExtractor().extract("https://example.com/jobs", HTML_FIXTURE)
            page = store.create_target_page(
                TargetPage(
                    target_id=target.id,
                    url=extracted.url,
                    page_type=extracted.page_type,
                    http_status=200,
                    title=extracted.title,
                    text=extracted.text,
                    metadata=extracted.metadata,
                )
            )
            evidence = store.add_evidence(
                Evidence(
                    target_id=target.id,
                    page_id=page.id,
                    source_url=page.url,
                    text="Werkstudent IT gesucht",
                    context_type=page.page_type,
                )
            )
            pages = store.list_target_pages(target.id)
        finally:
            store.close()

        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0].page_type, "career")
        self.assertEqual(evidence.page_id, page.id)


if __name__ == "__main__":
    unittest.main()
