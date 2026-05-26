from __future__ import annotations

import unittest

from target_radar.domain import TargetPage
from target_radar.engines.evidence import EvidenceEngine, EvidenceType


class EvidenceEngineTests(unittest.TestCase):
    def test_target_page_evidence_is_typed_and_tagged(self) -> None:
        page = TargetPage(
            id=7,
            target_id=3,
            url="https://example.com/kontakt",
            page_type="contact",
            title="Kontakt",
            text="Kontakt per Mail an hello@example.com",
        )

        evidence = EvidenceEngine().from_target_page(
            page,
            metadata={"emails": ["hello@example.com"]},
        )

        self.assertIsNotNone(evidence)
        assert evidence is not None
        self.assertEqual(evidence.context_type, "contact")
        self.assertEqual(evidence.priority, 80)
        self.assertEqual(evidence.metadata["evidence_type"], EvidenceType.TARGET_CONTACT)
        self.assertEqual(evidence.metadata["evidence_category"], EvidenceType.CONTACT)
        self.assertEqual(evidence.metadata["provenance"], "target_page")
        self.assertEqual(evidence.metadata["page_id"], 7)
        self.assertEqual(evidence.metadata["emails"], ["hello@example.com"])

    def test_context_source_evidence_keeps_source_provenance(self) -> None:
        context_source = {
            "id": 11,
            "source_query_id": 5,
            "pipeline_run_id": 2,
            "search_profile_id": 4,
            "use_case_id": 9,
            "use_case_slug": "company_osint",
            "query_text": "Solar Services Unternehmen Essen",
            "url": "https://www.regiomanager.de/ranking/solar/essen/",
            "domain": "regiomanager.de",
            "title": "Solar Dienstleister in Essen",
            "snippet": "Ranking mit mehreren lokalen Unternehmen.",
            "metadata": {
                "source_quality": {
                    "source_type": "directory",
                    "source_quality_score": 40,
                    "recommended_import_action": "review_source",
                }
            },
        }

        evidence = EvidenceEngine().from_context_source(
            target_id=3,
            context_source=context_source,
        )

        self.assertIsNotNone(evidence)
        assert evidence is not None
        self.assertEqual(evidence.context_type, "context_source")
        self.assertEqual(evidence.priority, 60)
        self.assertEqual(evidence.source_url, context_source["url"])
        self.assertIn("Solar Dienstleister", evidence.text)
        self.assertEqual(evidence.metadata["evidence_type"], EvidenceType.CONTEXT_DIRECTORY)
        self.assertEqual(evidence.metadata["evidence_category"], EvidenceType.REPUTATION)
        self.assertEqual(evidence.metadata["provenance"], "context_source")
        self.assertEqual(evidence.metadata["context_source_id"], 11)
        self.assertEqual(evidence.metadata["source_query_id"], 5)
        self.assertEqual(evidence.metadata["pipeline_run_id"], 2)
        self.assertEqual(evidence.metadata["source_type"], "directory")
        self.assertEqual(evidence.metadata["query_text"], "Solar Services Unternehmen Essen")


if __name__ == "__main__":
    unittest.main()
